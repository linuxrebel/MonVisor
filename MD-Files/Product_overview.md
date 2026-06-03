# MonVisor — Executive Product Overview

## The Problem

Organizations running modern infrastructure spend significant engineering time
configuring, maintaining, and troubleshooting their monitoring systems. Prometheus
and Grafana are the industry standard — powerful, open source, and widely adopted —
but they require deep expertise to configure correctly. New services go unmonitored.
Dashboards are built inconsistently. Alerts fire too often, or not at all. The
result is monitoring infrastructure that exists but doesn't deliver the visibility
the business needs.

## The Solution

MonVisor is an AI-powered monitoring advisor that automates the discovery,
configuration, and management of Prometheus-based monitoring environments.
It scans a network, identifies every service running in the environment, and
uses an embedded AI engine to generate correct, production-ready monitoring
configurations — scrape configs, alerting rules, and Grafana dashboards — tuned
to what was actually found.

## Key Value Propositions

**Speed.** What takes an experienced engineer one to three days takes MonVisor
minutes. Scan, review, generate, deploy.

**Accuracy.** Configurations are generated from a curated knowledge base of
monitoring best practices, not from trial and error.

**Security.** MonVisor runs entirely on the client's own infrastructure. No data
leaves the environment. No cloud dependency. No subscription lock-in.

**Accessibility.** Non-technical stakeholders can review monitoring decisions and
approve configurations through a browser-based interface. Engineers retain full
control via the command line.

**Longevity.** Knowledge updates are delivered as installable packages. As
Prometheus, Grafana, and the broader ecosystem evolve, MonVisor stays current
without requiring reconfiguration or retraining.

## Product Tiers

**Free Tier — CLI**
Network discovery, service identification, terminal and web-based review,
Prometheus and Alertmanager config generation, Grafana dashboard provisioning
from a stock library. Suitable for small teams and individual operators.

**Paid Tier — Professional**
Grafana-native review interface, automated config deployment via SSH,
custom AI-generated dashboards based on discovered services, enterprise
authentication (LDAP, Active Directory, Duo MFA, AWS IAM), and priority
knowledge update packages.

## Deployment Model

MonVisor installs on the Linux server where Prometheus runs. A built-in nginx
configuration puts Grafana and the MonVisor web interface behind a single
secure URL. Non-technical users access dashboards and approval workflows
through a browser. Engineers administer the tool via SSH and the command line.
Nothing is exposed to the internet beyond what the organization chooses to publish.

## Competitive Position

MonVisor occupies a unique position: it is not a SaaS monitoring product
competing with Datadog or New Relic, and it is not a generic AI assistant.
It is a purpose-built, locally-deployed tool that makes the open-source
monitoring stack — which clients already own — work the way it should.
The total cost of ownership is a one-time tool cost versus ongoing per-host
SaaS subscription fees, which at scale represents significant savings.
