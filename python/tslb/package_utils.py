"""
Tools for creating binary packages.
"""
import xml.etree.ElementTree as ET
from tslb import Architecture
from tslb import Constraint
from tslb import attribute_types


constr_type_str_map = {
        Constraint.CONSTRAINT_TYPE_EQ: 'eq',
        Constraint.CONSTRAINT_TYPE_NEQ: 'neq',
        Constraint.CONSTRAINT_TYPE_GT: 'gt',
        Constraint.CONSTRAINT_TYPE_LT: 'lt',
        Constraint.CONSTRAINT_TYPE_GTE: 'geq',
        Constraint.CONSTRAINT_TYPE_LTE: 'leq'
}


def desc_from_binary_package(bp, xml_declaration=True):
    """
    Create a desc.xml file from the given binary package. The function
    essentially adds the following entities to the file:

      * name, architecture, version and source version
      * runtime dependencies

    :param BinaryPackage bp: The binary package

    :param bool xml_declaration: If True, an XML declaration is prepended to
        the xml document's string. It does not have an encoding attribute.

    :raises attribute_types.AttributeType: If an attribute of the binary
        package has invalid type.
    :returns str: The xml content
    """
    root = ET.Element('pkg', {'file_version': '2.0'})

    # Basic information
    ET.SubElement(root, 'name').text = bp.name
    ET.SubElement(root, 'arch').text = Architecture.to_str(bp.architecture)
    ET.SubElement(root, 'version').text = str(bp.version_number)
    ET.SubElement(root, 'source_version').text = str(bp.source_package_version.version_number)

    # Add the runtime dependencies of the binary package
    rdeps = bp.get_attribute('rdeps')

    if rdeps.get_required():
        elem_deps = ET.SubElement(root, 'dependencies')

        for dep, constraints in rdeps.get_object_constraint_list():
            elem_dep = ET.SubElement(elem_deps, 'dep')
            ET.SubElement(elem_dep, 'name').text = dep
            ET.SubElement(elem_dep, 'arch').text = Architecture.to_str(bp.architecture)

            for constraint in constraints:
                if constraint.constraint_type != Constraint.CONSTRAINT_TYPE_NONE:
                    _type = constr_type_str_map[constraint.constraint_type]

                    ET.SubElement(elem_dep, 'constr', {'type': _type})\
                            .text = str(constraint.version_number)


    # Add references to triggers
    activated_triggers = _read_trigger_lists(bp, 'activated')
    interested_triggers = _read_trigger_lists(bp, 'interested')

    if activated_triggers or interested_triggers:
        trgs = ET.SubElement(root, 'triggers')

        for n in activated_triggers:
            ET.SubElement(trgs, 'activate').text = n

        for n in interested_triggers:
            ET.SubElement(trgs, 'interested').text = n


    # Convert the DOM to a xml string representation
    return '<?xml version="1.0"?>\n' + \
            ET.tostring(root, encoding='unicode')


def _read_trigger_lists(bp, trg_type):
    unqualified = trg_type + "_triggers"
    attrs = [unqualified] if bp.has_attribute(unqualified) else []
    attrs += bp.list_attributes(unqualified + "_*")

    trgs = set()
    for attr in attrs:
        l = bp.get_attribute(attr)
        try:
            attribute_types.ensure_package_manager_trigger_list(l)
        except attribute_types.InvalidAttributeType as e:
            raise attribute_types.InvalidAttributeType(e, attr) from e

        trgs |= set([e for e in l if e])

    return sorted(trgs)
