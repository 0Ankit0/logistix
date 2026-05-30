# Cloud Architecture

## Multi-Region Strategy

The Logistics Tracking System is deployed across three AWS regions to meet latency, regulatory, and resilience requirements:

| Region | Role | Rationale |
|---|---|---|
| `us-east-1` (N. Virginia) | **Primary** | Lowest AWS service coverage; US carrier API endpoints are geographically closest |
| `eu-west-1` (Ireland) | **EU Secondary** | GDPR compliance — EU consignee PII must not leave the EU region |
| `ap-southeast-1` (Singapore) | **APAC Secondary** | GPS processing optimised for APAC delivery networks; sub-100ms GPS ingest |

Global traffic routing is handled by Route53 GeoDNS: EU-origin requests route to `eu-west-1`, APAC requests route to `ap-southeast-1`, and all other regions default to `us-east-1`.

---

## Multi-Region Architecture Diagram

```mermaid
flowchart TB
  subgraph global["Global Layer"]
    R53[Route53 GeoDNS\nLatency-based routing]
    CF[CloudFront\nGlobal Distribution\nEdge Caching]
    R53 --> CF
  end

  subgraph useast1["us-east-1 (Primary - Full Stack)"]
    subgraph use1_app["Application Tier"]
      USE1_EKS[EKS Cluster\nAll 9 Services]
    end
    subgraph use1_data["Data Tier"]
      USE1_PG[(PostgreSQL Primary\nCloudNativePG)]
      USE1_TSDB[(TimescaleDB Primary\nGPS Breadcrumbs)]
      USE1_Redis[(Redis Cluster\n3M + 3R)]
      USE1_Kafka[(Kafka Cluster\n3 Brokers)]
      USE1_S3[(S3\nLabels + POD Images)]
    end
    USE1_EKS --> USE1_PG
    USE1_EKS --> USE1_TSDB
    USE1_EKS --> USE1_Redis
    USE1_EKS --> USE1_Kafka
  end

  subgraph euwest1["eu-west-1 (EU Secondary - GDPR Compliant)"]
    subgraph euw1_app["Application Tier"]
      EUW1_EKS[EKS Cluster\nAll 9 Services\nEU Data Residency]
    end
    subgraph euw1_data["Data Tier"]
      EUW1_PG[(PostgreSQL Primary\nEU PII Isolated)]
      EUW1_TSDB[(TimescaleDB\nEU GPS Data)]
      EUW1_Redis[(Redis Cluster)]
      EUW1_Kafka[(Kafka Cluster)]
      EUW1_S3[(S3 EU\nEU Labels + POD)]
    end
    EUW1_EKS --> EUW1_PG
    EUW1_EKS --> EUW1_TSDB
    EUW1_EKS --> EUW1_Redis
    EUW1_EKS --> EUW1_Kafka
  end

  subgraph apse1["ap-southeast-1 (APAC - GPS Optimised)"]
    subgraph apse1_app["Application Tier"]
      APSE1_EKS[EKS Cluster\ngps-processing-service\ntracking-service\nshipment-service]
    end
    subgraph apse1_data["Data Tier"]
      APSE1_TSDB[(TimescaleDB\nAPAC GPS Data)]
      APSE1_Kafka[(Kafka Cluster\nAPAC GPS Topics)]
      APSE1_Redis[(Redis Cache\nAPAC Vehicle Positions)]
    end
    APSE1_EKS --> APSE1_TSDB
    APSE1_EKS --> APSE1_Kafka
    APSE1_EKS --> APSE1_Redis
  end

  subgraph replication["Cross-Region Replication"]
    MM2[Kafka MirrorMaker2\nEvent Replication]
    S3REP[S3 Cross-Region\nReplication]
    PGREP[PostgreSQL\nLogical Replication\nAnalytics Read Replicas]
  end

  CF --> USE1_EKS
  CF --> EUW1_EKS
  CF --> APSE1_EKS

  USE1_Kafka -.MirrorMaker2.-> EUW1_Kafka
  USE1_Kafka -.MirrorMaker2.-> APSE1_Kafka
  APSE1_Kafka -.GPS events.-> USE1_Kafka
  EUW1_Kafka -.EU events.-> USE1_Kafka

  USE1_S3 -.cross-region replication.-> EUW1_S3
  USE1_PG -.logical replication\nanalytics only.-> EUW1_PG
```

---

## Data Sovereignty and GDPR Compliance

EU customer data (consignee name, address, contact details) must remain within `eu-west-1` at all times per GDPR Article 44. Implementation details:

- **EU shipments are created in `eu-west-1`** via GeoDNS routing for EU-origin requests.
- **PII fields are never replicated to `us-east-1`.** Kafka MirrorMaker2 is configured with a transform that redacts PII fields (`consignee_name`, `consignee_address`, `consignee_phone`) before cross-region replication. The primary region receives only operational data (shipment ID, status, timestamps, dimensions).
- **S3 label storage:** EU labels are stored in `s3://logistics-labels-eu-west-1` with S3 Object Lock (WORM) for regulatory compliance. Cross-region replication is **disabled** for EU label buckets.
- **Audit logs** are retained in EU CloudWatch Logs with a 7-year retention policy per GDPR record-keeping requirements.

---

## Edge Computing for GPS Processing

GPS devices (vehicle trackers, driver phones) send location pings at 1 Hz. At 10,000 active vehicles, this generates 10,000 events/second. Regional GPS processing reduces end-to-end latency to under 100ms:

```
GPS Device (APAC)
  → ap-southeast-1 GPS Ingest Endpoint (Route53 latency routing)
  → APAC gps-processing-service (validate, deduplicate, geofence)
  → APAC TimescaleDB (persisted <50ms)
  → APAC Kafka logistics.gps.location.v1
  → Kafka MirrorMaker2 (async replication to us-east-1)
  → us-east-1 tracking-service (aggregated view)
```

**Latency budget:**
- GPS device → APAC endpoint: ~20ms (regional routing)
- APAC GPS processing + TimescaleDB write: ~30ms
- Total GPS-to-persisted: **< 50ms** in APAC (vs ~150ms if routed to us-east-1)

Vehicle current-position (Redis cache) is also maintained per region, so tracking queries from APAC customers read from the local Redis cluster.

---

## Disaster Recovery

### RTO / RPO Targets

| Scenario | RTO | RPO | Strategy |
|---|---|---|---|
| Primary region (`us-east-1`) complete failure | 4 hours | 15 minutes | Promote `eu-west-1` to primary; redirect US traffic |
| Single AZ failure within `us-east-1` | 5 minutes | 0 (synchronous) | EKS multi-AZ scheduling; CloudNativePG synchronous replica |
| Single database node failure | 2 minutes | 0 (synchronous) | CloudNativePG automatic failover |
| Kafka broker failure | < 1 minute | 0 | Kafka ISR replication; partition leader re-election |

### DR Runbook Summary

1. **Detect:** Route53 health checks fail for `us-east-1` ALB for 2 consecutive 10-second checks.
2. **Alert:** PagerDuty SEV-1 page to on-call SRE within 30 seconds.
3. **Assess (0–15 min):** SRE validates failure scope via CloudWatch dashboard. If region-wide, proceed to step 4.
4. **Promote EU (15–60 min):**
   - Scale `eu-west-1` EKS cluster from steady-state (50% capacity) to full capacity via `eksctl scale nodegroup`.
   - Promote `eu-west-1` PostgreSQL replica to primary: `kubectl cnpg promote postgresql-eu -n infra`.
   - Update Route53 weighted records: set `us-east-1` weight to 0, `eu-west-1` weight to 100.
5. **Validate (60–90 min):** Run smoke tests against `eu-west-1` endpoints; confirm GPS pipeline flowing.
6. **Communicate (continuous):** Status page updated every 15 minutes; enterprise customers notified via account management.
7. **Restore (2–4 hrs):** Once `us-east-1` recovers, replay missed events from `eu-west-1` Kafka via MirrorMaker2 before switching traffic back.

---

## Cloud Services Mapping

| Component | AWS Service | Rationale |
|---|---|---|
| Container orchestration | EKS (Kubernetes 1.29) | Industry standard; rich ecosystem; Helm chart availability |
| PostgreSQL | CloudNativePG on EKS | Kubernetes-native operator; automatic failover; better than RDS for fine-grained config |
| GPS time-series storage | TimescaleDB on EKS (EC2) | Native Postgres extension; hypertable chunking for GPS data; chunk compression |
| Cache | Amazon ElastiCache (Redis 7) | Managed Redis cluster; Multi-AZ with automatic failover |
| Message streaming | Amazon MSK (Kafka 3.6) | Managed Kafka; integrates with IAM for auth; CloudWatch metrics built-in |
| Object storage (labels, POD) | Amazon S3 | Durable; S3 Object Lock for WORM compliance; lifecycle policies for tiering |
| CDN | CloudFlare (not CloudFront) | Superior DDoS protection; better edge caching for public tracking API |
| DNS | Amazon Route53 | GeoDNS for multi-region; health checks for automated failover |
| Load balancing | AWS ALB | Path-based routing; WAF integration; TLS offload |
| API Gateway | Kong (self-hosted on EKS) | Plugin ecosystem (JWT, rate-limit, transform); vendor independence |
| Secrets management | AWS Secrets Manager | Automatic rotation; Kubernetes External Secrets Operator for pod injection |
| Log aggregation | Amazon CloudWatch Logs | Native AWS integration; 7-year retention for compliance |
| Metrics | Prometheus + Amazon Managed Prometheus | Self-hosted Prometheus for scraping; AMP for long-term storage |
| Distributed tracing | AWS X-Ray + Jaeger | X-Ray for Lambda/ALB traces; Jaeger for Kubernetes service mesh traces |
| CI/CD | GitHub Actions + ArgoCD | GitOps via ArgoCD; GitHub Actions for build/test pipeline |
| Image registry | Amazon ECR | Native EKS auth; vulnerability scanning built-in |
| Certificate management | AWS ACM + cert-manager | ACM for ALB; cert-manager + Let's Encrypt for internal services |

---

## Cost Optimisation

| Strategy | Applies To | Estimated Saving |
|---|---|---|
| **Spot instances** for batch analytics workers | `analytics-service`, `route-optimization-service` off-peak | ~60% vs on-demand |
| **Reserved instances** (1-year) for stateful workloads | PostgreSQL, TimescaleDB, Redis EC2 instances | ~35% vs on-demand |
| **Savings Plans** for steady-state EKS worker nodes | Core `logistics-prod` worker node group | ~25% vs on-demand |
| **S3 Intelligent Tiering** for labels/POD older than 90 days | S3 buckets for label PDFs and POD images | ~40% storage cost |
| **TimescaleDB columnar compression** | `gps_breadcrumbs` chunks older than 24 hours | ~10x storage reduction |
| **CloudFront/CloudFlare caching** for public tracking API | `/v1/track/*` responses | Reduces origin requests ~80% |

