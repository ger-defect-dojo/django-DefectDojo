import logging
import re

import dateutil
from defusedxml import ElementTree

from dojo.models import Finding
from dojo.tools.cyclonedx.helpers import Cyclonedxhelper

LOGGER = logging.getLogger(__name__)


class CycloneDXXMLParser:
    def _get_findings_xml(self, file, test):
        nscan = ElementTree.parse(file)
        root = nscan.getroot()
        namespace = self.get_namespace(root)
        if not namespace.startswith("{http://cyclonedx.org/schema/bom/"):
            msg = f"This doesn't seem to be a valid CycloneDX BOM XML file. Namespace={namespace}"
            raise ValueError(msg)
        ns = {
            "b": namespace.replace("{", "").replace(
                "}", "",
            ),  # we accept whatever the version
            "v": "http://cyclonedx.org/schema/ext/vulnerability/1.0",
        }
        # get report date
        report_date = None
        report_date_raw = root.findtext(
            "b:metadata/b:timestamp", namespaces=ns,
        )
        if report_date_raw:
            report_date = dateutil.parser.parse(report_date_raw)
        bom_refs = {}
        findings = []
        for component in root.findall(
            "b:components/b:component", namespaces=ns,
        ):
            component_name = component.findtext(f"{namespace}name")
            component_version = component.findtext(f"{namespace}version")
            # save a ref
            if "bom-ref" in component.attrib:
                bom_refs[component.attrib["bom-ref"]] = {
                    "name": component_name,
                    "version": component_version,
                }
            # for each vulnerabilities add a finding
            for vulnerability in component.findall(
                "v:vulnerabilities/v:vulnerability", namespaces=ns,
            ):
                finding_vuln = self.manage_vulnerability_legacy(
                    vulnerability,
                    ns,
                    bom_refs,
                    report_date=report_date,
                    component_name=component_name,
                    component_version=component_version,
                )
                findings.append(finding_vuln)
        # manage adhoc vulnerabilities
        for vulnerability in root.findall(
            "v:vulnerabilities/v:vulnerability", namespaces=ns,
        ):
            finding_vuln = self.manage_vulnerability_legacy(
                vulnerability, ns, bom_refs, report_date,
            )
            findings.append(finding_vuln)
        # manage adhoc vulnerabilities (compatible with 1.4 of the spec)
        for vulnerability in root.findall(
            "b:vulnerabilities/b:vulnerability", namespaces=ns,
        ):
            findings.extend(
                self._manage_vulnerability_xml(
                    vulnerability, ns, bom_refs, report_date,
                ),
            )
        return findings

    def get_namespace(self, element):
        """Extract namespace present in XML file."""
        m = re.match(r"\{.*\}", element.tag)
        return m.group(0) if m else ""

    def manage_vulnerability_legacy(
        self,
        vulnerability,
        ns,
        bom_refs,
        report_date,
        component_name=None,
        component_version=None,
    ):
        ref = vulnerability.attrib["ref"]
        vuln_id = vulnerability.findtext("v:id", namespaces=ns)

        severity = vulnerability.findtext(
            "v:ratings/v:rating/v:severity", namespaces=ns,
        )
        description = vulnerability.findtext("v:description", namespaces=ns)
        # by the schema, only id and ref are mandatory, even the severity is
        # optional
        if not description:
            description = "\n".join(
                [
                    f"**Ref:** {ref}",
                    f"**Id:** {vuln_id}",
                    f"**Severity:** {severity}",
                ],
            )
        if component_name is None:
            bom = bom_refs[ref]
            component_name = bom["name"]
            component_version = bom["version"]

        severity = Cyclonedxhelper().fix_severity(severity)
        references = ""
        for adv in vulnerability.findall(
            "v:advisories/v:advisory", namespaces=ns,
        ):
            references += f"{adv.text}\n"
        finding = Finding(
            title=f"{component_name}:{component_version} | {vuln_id}",
            description=description,
            severity=severity,
            references=references,
            component_name=component_name,
            component_version=component_version,
            vuln_id_from_tool=vuln_id,
            nb_occurences=1,
        )
        if report_date:
            finding.date = report_date
        mitigation = ""
        for recommend in vulnerability.findall(
            "v:recommendations/v:recommendation", namespaces=ns,
        ):
            mitigation += f"{recommend.text}\n"
        if mitigation != "":
            finding.mitigation = mitigation
        # manage CVSS
        for rating in vulnerability.findall(
            "v:ratings/v:rating", namespaces=ns,
        ):
            if rating.findtext("v:method", namespaces=ns) == "CVSSv3":
                raw_vector = rating.findtext("v:vector", namespaces=ns)
                severity = rating.findtext("v:severity", namespaces=ns)
                cvssv3 = Cyclonedxhelper()._get_cvssv3(raw_vector)
                if cvssv3:
                    finding.cvssv3 = cvssv3.clean_vector()
                    if severity:
                        finding.severity = Cyclonedxhelper().fix_severity(severity)
                    else:
                        finding.severity = cvssv3.severities()[0]
        # if there is some CWE
        cwes = self.get_cwes(vulnerability, "v", ns)
        if len(cwes) > 1:
            # TODO: support more than one CWE
            LOGGER.debug(
                f"more than one CWE for a finding {cwes}. NOT supported by parser API",
            )
        if len(cwes) > 0:
            finding.cwe = cwes[0]
        vulnerability_ids = []
        # set id as first vulnerability id
        if vuln_id:
            vulnerability_ids.append(vuln_id)
        if vulnerability_ids:
            finding.unsaved_vulnerability_ids = vulnerability_ids
        return finding

    def get_cwes(self, node, prefix, namespaces):
        return [int(cwe.text) for cwe in node.findall(
            prefix + ":cwes/" + prefix + ":cwe", namespaces,
        ) if cwe.text.isdigit()]

    def _manage_vulnerability_xml(
        self,
        vulnerability,
        ns,
        bom_refs,
        report_date,
        component_name=None,
        component_version=None,
    ):
        vuln_id = vulnerability.findtext("b:id", namespaces=ns)
        description = vulnerability.findtext("b:description", namespaces=ns)
        detail = vulnerability.findtext("b:detail", namespaces=ns)
        if detail:
            if description:
                description += f"\n{detail}"
            else:
                description = f"\n{detail}"
        severity = vulnerability.findtext(
            "b:ratings/b:rating/b:severity", namespaces=ns,
        )
        severity = Cyclonedxhelper().fix_severity(severity)
        references = ""
        for advisory in vulnerability.findall(
            "b:advisories/b:advisory", namespaces=ns,
        ):
            title = advisory.findtext("b:title", namespaces=ns)
            if title:
                references += f"**Title:** {title}\n"
            url = advisory.findtext("b:url", namespaces=ns)
            if url:
                references += f"**URL:** {url}\n"
            references += "\n"
        vulnerability_ids = []
        # set id as first vulnerability id
        if vuln_id:
            vulnerability_ids.append(vuln_id)
        # check references to see if we have other vulnerability ids
        for reference in vulnerability.findall(
            "b:references/b:reference", namespaces=ns,
        ):
            vulnerability_id = reference.findtext("b:id", namespaces=ns)
            if vulnerability_id:
                vulnerability_ids.append(vulnerability_id)
        # for all component affected
        findings = []
        for target in vulnerability.findall(
            "b:affects/b:target", namespaces=ns,
        ):
            ref = target.find("b:ref", namespaces=ns)
            component_name, component_version = Cyclonedxhelper()._get_component(
                bom_refs, ref.text,
            )
            finding = Finding(
                title=f"{component_name}:{component_version} | {vuln_id}",
                description=description,
                severity=severity,
                mitigation=vulnerability.findtext(
                    "b:recommendation", namespaces=ns,
                ),
                references=references,
                component_name=component_name,
                component_version=component_version,
                static_finding=True,
                dynamic_finding=False,
                vuln_id_from_tool=vuln_id,
                nb_occurences=1,
            )
            if vulnerability_ids:
                finding.unsaved_vulnerability_ids = vulnerability_ids
            if report_date:
                finding.date = report_date
            # manage CVSS
            for rating in vulnerability.findall(
                "b:ratings/b:rating", namespaces=ns,
            ):
                method = rating.findtext("b:method", namespaces=ns)
                if method == "CVSSv3" or method == "CVSSv31":
                    raw_vector = rating.findtext("b:vector", namespaces=ns)
                    severity = rating.findtext("b:severity", namespaces=ns)
                    cvssv3 = Cyclonedxhelper()._get_cvssv3(raw_vector)
                    if cvssv3:
                        finding.cvssv3 = cvssv3.clean_vector()
                        if severity:
                            finding.severity = Cyclonedxhelper().fix_severity(severity)
                        else:
                            finding.severity = cvssv3.severities()[0]
            # if there is some CWE. Check both for old namespace and for 1.4
            cwes = self.get_cwes(vulnerability, "v", ns)
            if not cwes:
                cwes = self.get_cwes(vulnerability, "b", ns)
            if len(cwes) > 1:
                # TODO: support more than one CWE
                LOGGER.debug(
                    f"more than one CWE for a finding {cwes}. NOT supported by parser API",
                )
            if len(cwes) > 0:
                finding.cwe = cwes[0]
            # Check for mitigation
            analysis = vulnerability.findall("b:analysis", namespaces=ns)
            if analysis and len(analysis) == 1:
                state = analysis[0].findtext("b:state", namespaces=ns)
                if state:
                    if (
                        state == "resolved"
                        or state == "resolved_with_pedigree"
                        or state == "not_affected"
                    ):
                        finding.is_mitigated = True
                        finding.active = False
                    elif state == "false_positive":
                        finding.false_p = True
                        finding.active = False
                    if not finding.active:
                        detail = analysis[0].findtext(
                            "b:detail", namespaces=ns,
                        )
                        if detail:
                            finding.mitigation += f"\n**This vulnerability is mitigated and/or suppressed:** {detail}\n"
            findings.append(finding)
        return findings
