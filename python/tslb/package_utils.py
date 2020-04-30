"""
Tools for creating binary packages.
"""
import xml.etree.ElementTree as ET
from tslb import Architecture


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

    # Convert the DOM to a xml string representation
    return '<?xml version="1.0"?>\n' + \
            ET.tostring(root, encoding='unicode')
