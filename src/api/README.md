# Diligence OS — API (pre-gate scaffold)

**Status: lives on the `feat/api-scaffold` branch only. Not merged to
`main`, deliberately** — issues #28/#29 gate this work on the Month 1
go/pivot/kill decision (#19). This scaffold exists so the stack decisions
are settled and tested, not because the API is a POC deliverable.

Kotlin on Quarkus, read-only over the Postgres **fact table** that the
Python pipeline (`src/diligence/`) writes. Python owns the schema and all
production writes until #29; the Flyway migration here is a documented
byte-mirror of `src/diligence/facts/db.py` so tests and fresh
environments get the table.

## Endpoints

- `GET /api/v1/datarooms` — dataroom/tier inventory with fact, document
  and needs-review counts
- `GET /api/v1/datarooms/{dataroom}/facts?tier=&factType=&minConfidence=`
  — facts with full provenance (source doc, page, confidence) — no fact
  leaves the API without it
- `GET /api/v1/datarooms/{dataroom}/sufficiency?tier=&bankMonths=&vatQuarters=&fys=`
  — document sufficiency score; faithful Kotlin port of
  `src/diligence/report/sufficiency.py`, pinned by a cross-language test
  (the 23/100 thin-room case)
- `GET /q/health` — liveness/readiness

## Toolchain

- **Quarkus 3.22.3** (latest stable on Maven Central — the "3.33 LTS"
  from the original agent notes does not exist), Kotlin 2.1, Java 21
  bytecode.
- Gradle 8.14 wrapper. `gradle/gradle-daemon-jvm.properties` pins the
  **daemon** to a JDK 21 toolchain, so `./gradlew` works from a JDK 25
  shell (the launcher JVM) without `org.gradle.java.home` hacks — never
  commit that property.

```bash
./gradlew test          # Dev Services spins an ephemeral Postgres (Docker required)
./gradlew quarkusDev    # dev mode on :8082 against localhost:5433 (docker compose up -d)
./gradlew build         # full build
```

Dev/prod point at the same Postgres the pipeline uses
(`localhost:5433/diligence`, or `DATABASE_JDBC_URL`). Tests never touch
it — Dev Services provisions a throwaway container and Flyway
`clean-at-start` resets it.

## Invariants carried over from the Python core

- Money is integer pence (`value_pence BIGINT`).
- Provenance NOT NULL; `confidence < 0.8` (CONFIDENCE_REVIEW_THRESHOLD,
  kept equal to `facts/model.py`) means quarantined-for-review.
- `quarkus.hibernate-orm.database.generation=validate` — never anything
  else; migrations are additive and mirror Python until #29.
