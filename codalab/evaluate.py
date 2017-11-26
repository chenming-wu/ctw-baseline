# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import settings
import subprocess
import sys

from pythonapi import eval_tools


def main():
    submit_dir, truth_dir, output_dir = sys.argv[1:]

    with open(os.path.join(truth_dir, 'meta.json')) as f:
        meta_info = json.load(f)
    if meta_info['task'] == 'detection':
        submit_file = None
        for file_name in sorted(os.listdir(submit_dir)):
            file_path = os.path.join(submit_dir, file_name)
            if file_name.endswith('.jsonl') and os.path.isfile(file_path):
                submit_file = file_path
                break
        assert submit_file is not None, '*.jsonl not found'
        run_detection(submit_file, output_dir, meta_info['split'], meta_info['aes_key'])
    else:
        raise NotImplementedError('task='.format(meta_info['task']))


def run_detection(submit_file, output_dir, split, aes_key):
    exe = '/tmp/evalwrap.bin'
    p = subprocess.Popen(['g++', 'evalwrap.cpp', '-std=c++11', '-O2', '-Wno-all', '-o', exe])
    assert 0 == p.wait()
    p1 = subprocess.Popen(['openssl', 'aes-256-cbc', '-in', settings.TEST_DETECTION_GT_AES, '-k', aes_key, '-d'],
        stdout=subprocess.PIPE) #, stderr=subprocess.PIPE)
    p2 = subprocess.Popen([exe, submit_file], stdin=p1.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()
    report_str = p2.communicate()[0].decode('utf-8')
    assert 0 == p1.wait()
    assert 0 == p2.wait()

    report = json.loads(report_str)
    assert 0 == report['error'], report['msg']

    performance = report['performance']
    print(json.dumps(performance, sort_keys=True, indent=2))

    scores = list()
    for szname, _ in settings.SIZE_RANGES:
        scores.append(('{}_mAP_macro'.format(szname), performance[szname]['mAP']))
        scores.append(('{}_mAP_micro'.format(szname), performance[szname]['mAP_micro']))
        scores.append(('{}_AP'.format(szname), performance[szname]['AP']))
        n = rc = 0
        for o in performance[szname]['attributes']:
            n += o['n']
            rc += o['recall']
        rc = 0. if n == 0 else rc / n
        scores.append(('{}_Recall'.format(szname), rc))

    def check(k, attr_id):
        if attr_id < len(settings.ATTRIBUTES):
            return int(k) & 2 ** attr_id
        else:
            return 0 == int(k) & 2 ** (attr_id - len(settings.ATTRIBUTES))
    def trans(attr_id):
        if attr_id < len(settings.ATTRIBUTES):
            return settings.ATTRIBUTES[attr_id]
        else:
            return 'not_{}'.format(settings.ATTRIBUTES[attr_id - len(settings.ATTRIBUTES)])
    for i in range(2 * len(settings.ATTRIBUTES)):
        n = rc = 0
        for k, o in enumerate(performance['all']['attributes']):
            if check(k, i):
                n += o['n']
                rc += o['recall']
        rc = 0. if n == 0 else rc / n
        scores.append(('all_Recall_{}'.format(trans(i)), rc))

    output_path = os.path.join(output_dir, 'scores.txt')
    with open(output_path, 'w') as f:
        for k, v in scores:
            f.write('{:s}: {:f}\n'.format(k, v * 100))

    output_html = os.path.join(output_dir, 'scores.html')
    with open(output_html, 'w') as f:
        f.write('<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta http-equiv="X-UA-Compatible" content="IE=Edge"></head>'
            '<body><h2>Detailed results</h2>'
            '<iframe style="height: 80%; width: 100%; border: 0;" src="https://ctwdataset.github.io/resource/codalab/templates/detection_detailed_results_iframe.html"></iframe>'
            '</body></html>')


if __name__ == '__main__':
    main()