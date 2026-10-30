import unittest

from pulse_topology import coobserved_dependencies


class DependencyCorrelationTests(unittest.TestCase):
    @staticmethod
    def item(host, service, severity, depends_on=""):
        return {
            "host": host, "name": service, "state": "running",
            "severity": severity,
            "labels": {"project": "demo", "service": service,
                       "depends_on": depends_on},
        }

    def test_only_explicit_edge_on_same_host(self):
        entries = [
            self.item("a", "api", "critical", "db:service_healthy:false"),
            self.item("a", "db", "warn"),
            self.item("b", "api", "critical", "db:service_healthy:false"),
            self.item("b", "db", "ok"),
        ]
        result = coobserved_dependencies(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["host"], "a")
        self.assertEqual(result[0]["assessment"], "co_observed_warning_not_cause")

    def test_unknown_and_missing_target_not_outage(self):
        entries = [self.item("a", "api", "critical", "db:service_healthy:false"),
                   self.item("a", "db", "unknown")]
        self.assertEqual(coobserved_dependencies(entries), [])
        self.assertEqual(coobserved_dependencies(entries[:1]), [])

    def test_shared_project_does_not_prove_dependency(self):
        entries = [self.item("a", "api", "critical"), self.item("a", "db", "critical")]
        self.assertEqual(coobserved_dependencies(entries), [])


if __name__ == "__main__":
    unittest.main()
