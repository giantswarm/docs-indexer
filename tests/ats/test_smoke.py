"""ATS smoke for the docs-indexer-app chart.

app-test-suite (>= 1.0) applies the cluster prerequisites, installs the
packaged chart on the job's kind cluster with `helm upgrade --install --wait`
(tests/test-values.yaml, namespace from .ats/main.yaml) and then runs this file
with `pytest -m smoke`. The smoke is the chart-level install check: the
cluster is reachable and the chart's four indexer CronJobs exist, scheduled and
not suspended. The chart has no Deployment; the CronJobs are not run here.
"""

import logging
import os

import pykube
import pytest
from pytest_helm_charts.clusters import Cluster

logger = logging.getLogger(__name__)

# ATS sets ATS_RELEASE_NAMESPACE (docs/TEST_CONTRACT.md in app-test-suite); the
# fallback is app-tests-deploy-namespace in .ats/main.yaml.
NAMESPACE = os.environ.get("ATS_RELEASE_NAMESPACE", "docs-indexer")
# `<.Values.name>-<site>`, one CronJob per template in helm/docs-indexer-app.
CRONJOBS = [
    f"docs-indexer-app-{site}" for site in ("blog", "docs", "handbook", "intranet")
]


@pytest.mark.smoke
def test_api_working(kube_cluster: Cluster) -> None:
    """The kind cluster ATS runs against is reachable."""
    assert kube_cluster.kube_client is not None
    assert len(pykube.Node.objects(kube_cluster.kube_client)) >= 1


@pytest.mark.smoke
@pytest.mark.upgrade
def test_cronjobs_installed(kube_cluster: Cluster) -> None:
    """Every indexer CronJob exists, carries a schedule and is not suspended."""
    cronjob = pykube.object_factory(kube_cluster.kube_client, "batch/v1", "CronJob")
    found = {
        c.name: c
        for c in cronjob.objects(kube_cluster.kube_client).filter(namespace=NAMESPACE)
    }
    missing = sorted(set(CRONJOBS) - set(found))
    assert not missing, (
        f"CronJobs missing in {NAMESPACE}: {missing} (found: {sorted(found)})"
    )
    for name in CRONJOBS:
        spec = found[name].obj["spec"]
        assert spec.get("schedule"), f"{name} has no schedule"
        assert not spec.get("suspend", False), f"{name} is suspended"
        logger.info("CronJob %s/%s scheduled '%s'", NAMESPACE, name, spec["schedule"])
