"""
Tools for creating binary packages.
"""
import xml.etree.ElementTree as ET
from tslb import Architecture
from tslb import Constraint


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


    # Convert the DOM to a xml string representation
    return '<?xml version="1.0"?>\n' + \
            ET.tostring(root, encoding='unicode')
