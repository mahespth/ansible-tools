# Initial Version to discuss with Redhat.

FROM ansible-automation-platform-25/ee-supported-rhel9:latest AS galaxy

RUN \
  sed -i -e 's/gpgcheck = 1/gpgcheck = 1\nsslverify = 0/g' /etc/yum.repos.d/ubi.repo

RUN \
  https_proxy=${PROXY} \
  microdnf install -y gcc python3.11-devel net-snmp-devel net-snmp-libs

RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
  GIT_SSL_NO_VERIFY=true \
  https_proxy=${PROXY} \
  pip3.11 install \
    --use-pep517 \
    --requirement /tmp/requirements.txt \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org

RUN \
  https_proxy=${PROXY} \
  microdnf install  -y net-snmp net-snmp-utils #python3-net-snmp

ENV DESCRIPTION="Red Hat Ansible Automation Platform Extended Container" \
    container=oci

LABEL com.redhat.component="ee-supported-extended-container" \
      name="ansible-automation-platform-25/ee-supported-extended-rhel9" \
      version="2.5.0" \
      summary="${DESCRIPTION}" \
      io.openshift.expose-services="" \
      io.openshift.tags="automation,ansible" \
      io.k8s.display-name="ee-supported-extended-rhel9" \
      maintainer="mahespth" \
      description="${DESCRIPTION}"

