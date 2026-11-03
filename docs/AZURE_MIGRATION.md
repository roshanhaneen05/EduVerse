# EduVerse Azure Production Migration Architecture

This roadmap describes how the local EduVerse application transitions to a scalable, secure Microsoft Azure production architecture without changing core application business logic.

---

## 1. Target Cloud Architecture

```
                                  +------------------------------------+
                                  |         Azure Front Door /         |
                                  |     Application Gateway (WAF)      |
                                  +------------------------------------+
                                                     |
                                   HTTPS TLS 1.3 / Custom Domain / SSL
                                                     |
                         +---------------------------+---------------------------+
                         |                                                       |
                         v                                                       v
        +--------------------------------+                      +--------------------------------+
        |   Azure Static Web Apps / CDN  |                      |  Azure Kubernetes Service(AKS) |
        |     Angular Frontend SPA       |                      |  or Azure Container Apps (ACA) |
        +--------------------------------+                      |   FastAPI Backend Instances    |
                                                                +--------------------------------+
                                                                                 |
                                             +-----------------------------------+--------------------+
                                             |                                   |                    |
                                             v                                   v                    v
                              +----------------------------+     +------------------------+  +--------------------+
                              |  Azure Database for        |     |     Azure Key Vault    |  | Azure OpenAI /     |
                              |   PostgreSQL (Flexible)    |     |  Secrets, Keys, Certs  |  | Cognitive Services |
                              +----------------------------+     +------------------------+  +--------------------+
```

---

## 2. Infrastructure as Code (Terraform / Bicep)

1. **Resource Group**: Centralized isolation boundary for all EduVerse services.
2. **Azure Container Registry (ACR)**: Private container image repository with vulnerability scanning via Microsoft Defender for Cloud.
3. **Azure Kubernetes Service (AKS)**: Managed Kubernetes cluster running backend pods with Horizontal Pod Autoscaling (HPA).
4. **Azure Database for PostgreSQL (Flexible Server)**: Multi-zone resilient database with automated backups and private endpoints.
5. **Azure Key Vault**: Stores `SECRET_KEY`, database credentials, and external AI provider keys; injected into AKS pods via Azure Secrets Store CSI Driver.

---

## 3. GitOps Deployment Pipeline with Flux CD

1. **Repository Structure**: Monorepo or separate repositories for application code and Kubernetes manifests (`k8s/`).
2. **Helm Charts**: Templatized deployment manifests for backend service, ingress routing, configmaps, and secrets.
3. **Flux CD Controller**: Runs inside AKS, continuously reconciling git state with the live cluster.
4. **Zero-Downtime Rollouts**: Rolling updates configured with readiness and liveness probes tied to `/health`.

---

## 4. Observability & Monitoring

- **Prometheus & Grafana**: Scrapes application metrics and cluster utilization.
- **Azure Monitor & Log Analytics**: Centralized application logging and distributed tracing.
- **Alerting**: Automated notifications on error rate spikes or degraded database connectivity.

