import sys
import json
from lxml import etree
import urllib2
import base64
import argparse


BASE_STASH_URI = '/projects/%s/repos/%s/pull-requests/%s/diff?contextLines=0&whitespace=ignore-all&withComments=false'

class StashApi:

    def __init__(self, base_stash_url, stash_user, stash_pw):
        self.stash_api_url = base_stash_url
        self.stash_user = stash_user
        self.stash_pw = stash_pw

    def get_pull_request_info(self, project, repo_name, pr_number):
        url = self.stash_api_url + (BASE_STASH_URI % (project, repo_name, pr_number))
        req = urllib2.Request(url)
        base64string = base64.encodestring('%s:%s' % (self.stash_user, self.stash_pw))
        req.add_header('Authorization', 'Basic %s' % base64string.strip())
        resp = urllib2.urlopen(req, timeout=20)
        return json.loads(resp.read())


class CoverageReporter:

    def __init__(self, stash_repo_diff, clover_xml, base_repo_path):
        self.stash_repo_diff = stash_repo_diff
        self._parse(clover_xml, base_repo_path)

    def _parse(self, clover_xml, base_repo_path):
        with open(clover_xml, 'r+') as f:
            coverage_xml = etree.fromstring(f.read())
        file_diffs = {}
        for diff in self.stash_repo_diff['diffs']:
            file_name = diff['destination']['toString']
            added_lines = {}
            for hunk in diff['hunks']:
                for seg in hunk['segments']:
                    if seg['type'] != 'ADDED':
                        continue
                    for line in seg['lines']:
                        xpath = ('//file[@name=\'%s\']/line[@num=%s]' % (base_repo_path + file_name, line['destination']))
                        covered_line = coverage_xml.xpath(xpath)
                        # only consider statements
                        if len(covered_line) == 0 or covered_line[0].get('type') != 'stmt':
                            continue
                        covered_line = covered_line[0]
                        covered = (covered_line.get('count') > 0)
                        added_lines[covered_line.get('num')] = covered
            file_diffs[file_name] = added_lines
        self.file_diffs = file_diffs

    def get_total_coverage(self):
        total_lines = 0
        covered_lines = 0
        for key in self.file_diffs:
            total_lines += len(self.file_diffs[key])
            covered_lines += len(filter(lambda x: self.file_diffs[key][x], self.file_diffs[key]))
        if total_lines == 0:
            return 100
        return (covered_lines / float(total_lines)) * 100

    def get_file_coverage_lines(self):
        return self.file_diffs

    def __str__(self):
        s = 'Total Coverage Pct: %s' % self.get_total_coverage()
        for f_name in self.file_diffs:
            if len(self.file_diffs[f_name].values()) == 0:
                #probs a test file, either way, nothing of consequence in it
                continue
            uncovered_lines = filter(lambda x: not self.file_diffs[f_name][x], self.file_diffs[f_name])
            cov_pct = (1 - (len(uncovered_lines) / float(len(self.file_diffs[f_name].values())))) * 100
            s += '\n\t%s: %s' % (f_name, cov_pct)
            if len(uncovered_lines) > 0:
                s += '\n\t\tUncovered Line Numbers: %s' % ', '.join(str(x) for x in uncovered_lines)
        return s

    __repr__ = __str__


def main(argv):
    parser = argparse.ArgumentParser(description='PR code coverage', prog='coverage.py')
    parser.add_argument('-x', '--clover-xml', help='clover code coverage report', required=True)
    parser.add_argument('-p', '--stash-project', help='project', required=True)
    parser.add_argument('-n', '--repo-name', help='stash repo name', required=True)
    parser.add_argument('-i', '--pr-id', help='pull request id', required=True)
    parser.add_argument('-b', '--base-repo-path', help='path to repo', required=True)
    parser.add_argument('-s', '--stash-api', help='stash api url', required=True)
    parser.add_argument('-u', '--stash-user', help='stash api user', required=True)
    parser.add_argument('-w', '--stash-password', help='stash api password', required=True)
    args = parser.parse_args(argv)
    stash_api = StashApi(args.stash_api, args.stash_user, args.stash_password)
    stash_repo_diff = stash_api.get_pull_request_info(args.stash_project, args.repo_name, args.pr_id)
    c = CoverageReporter(stash_repo_diff, args.clover_xml, args.base_repo_path)
    print c


if __name__ == '__main__':
    main(sys.argv[1:])
