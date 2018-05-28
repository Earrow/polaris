from lxml import etree

from ..tools import NestDict


def nose_analysis(ret_file):
    tree = etree.parse(ret_file)

    ret = NestDict()

    for suite in tree.xpath('//testsuite'):
        suite_name = suite.xpath('./@name')[0]
        ret['testsuites'][suite_name]['tests'] = int(tree.xpath('//testsuite/@tests')[0])
        ret['testsuites'][suite_name]['errors'] = int(tree.xpath('//testsuite/@errors')[0])
        ret['testsuites'][suite_name]['failures'] = int(tree.xpath('//testsuite/@failures')[0])
        ret['testsuites'][suite_name]['skip'] = int(tree.xpath('//testsuite/@skip')[0])

        for case in suite.xpath('./testcase'):
            case_class_name = case.xpath('./@classname')[0]
            case_name = case.xpath('./@name')[0]

            if case.xpath('./failure'):
                failure = case.xpath('./failure')[0]
                ret['testsuites'][suite_name][case_class_name][case_name]['failure']['type'] = failure.xpath('./@type')[
                    0].replace('\n', '')
                ret['testsuites'][suite_name][case_class_name][case_name]['failure']['message'] = \
                    failure.xpath('./@message')[0].replace('\n', '')
                ret['testsuites'][suite_name][case_class_name][case_name]['failure']['trace'] = \
                    failure.xpath('./text()')[0]

            if case.xpath('./system-out'):
                system_out = case.xpath('./system-out')[0]
                ret['testsuites'][suite_name][case_class_name][case_name]['system_out'] = system_out.xpath('./text()')[
                    0]

    return ret


if __name__ == '__main__':
    print(nose_analysis('/home/hcliu/Documents/python_projects/polaris/app/job/1.xml'))
