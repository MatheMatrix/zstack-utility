
from zstacklib.utils import log, linux


logger = log.get_logger(__name__)
MULTIPATH_PATH = "/etc/multipath.conf"


def parse_multipath_conf(conf_lines):
    # type: (iter) -> list[dict[str, list]]

    config = []
    for line in conf_lines:
        line = line.rstrip().strip()
        if line.startswith('#'):
            continue
        elif line.endswith('{'):
            config.append({line.replace(' ', '').split("{")[0]: parse_multipath_conf(conf_lines)})
        else:
            if line.endswith('}'):
                break
            else:
                line = line.split()
                if len(line) > 1:
                    config.append({line[0]: (" ".join(line[1:])).strip('"')})
    return config


def sorted_conf(sections):
    # type: (list) -> list

    result = []
    if not sections:
        return result

    for section in sorted(sections, key=lambda s: s.keys()[0]):
        section_name, section_value = section.items()[0]
        if type(section_value) is list:
            result.append({section_name: sorted_conf(section_value)})
        else:
            result.append({section_name: section_value})

    return result

class MultipathConfigUpdater:
    def __init__(self, config_path):
        self.config_path = config_path
        self.modified = False
        with open(config_path, 'r+') as fd:
            self.config = parse_multipath_conf(fd)

    def set_default_config(self):
        default_device = {'device': [{'features': '0'}, {'no_path_retry': 'fail'}, {'product': '.*'}, {'vendor': '.*'}]}
        default_find_multipaths = {"find_multipaths": "yes"}
        feature_to_remove = 'queue_if_no_path'

        has_devices_section = False
        has_default_device = False
        has_defaults_section = False
        for section in self.config:
            if 'defaults' in section:
                has_defaults_section = True
                for attribute in section['defaults']:
                    name, value = attribute.items()[0]
                    if name == "find_multipaths":
                        section["defaults"].remove(attribute)
                        self.modified |= value.strip().strip('"') != 'yes'

                section["defaults"].append(default_find_multipaths)


            if 'devices' in section:
                has_devices_section = True
                for subsection in section['devices']:
                    for attribute in subsection['device'][:]:
                        name, value = attribute.items()[0]
                        if value.strip().strip('"') == '*':
                            attribute[name] = '.*'
                            self.modified = True

                        if name == 'features' and feature_to_remove in value:
                            subsection['device'].remove(attribute)
                            self.modified = True

                        if cmp(sorted(default_device['device']), sorted(subsection['device'])) == 0:
                            has_default_device = True

                if not has_default_device:
                    section['devices'].append(default_device)
                    self.modified = True

        if not has_defaults_section:
            self.config.append({'defaults': [default_find_multipaths]})
            self.modified = True

        if not has_devices_section:
            self.config.append({'devices': [default_device]})
            self.modified = True


    def config_section(self, name, cfg):
        for section in self.config:
            if name not in section:
                continue
            elif cmp(sorted_conf(section[name]), sorted_conf(cfg)) == 0:
                return
            else:
                self.config.remove(section)
                self.config.append({name: cfg})
                self.modified = True
                break

    def save(self):
        logger.info(self.config)
        if not self.modified:
            return

        with open(self.config_path, 'r+') as fd:
            fd.seek(0)
            fd.truncate()

            for section in self.config:
                section_name, section_value = section.items()[0]
                fd.write("%s {\n" % section_name)
                for child in sorted_conf(section_value):
                    child_name, child_value = child.items()[0]
                    # child is attribute
                    if type(child_value) == str:
                        fd.write('\t%s "%s"\n' % (child_name.strip('"'), child_value.strip('"')))
                        continue

                    # child is subsection
                    fd.write('\t%s {\n' % child_name)
                    for attribute in child_value:
                        attrib_name, attrib_value = attribute.items()[0]
                        fd.write('\t\t%s "%s"\n' % (attrib_name.strip('"'), attrib_value.strip('"')))
                    fd.write("\t}\n")
                fd.write("}\n")