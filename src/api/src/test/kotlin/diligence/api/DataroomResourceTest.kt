package diligence.api

import com.fasterxml.jackson.databind.node.JsonNodeFactory
import diligence.api.fact.Fact
import io.quarkus.narayana.jta.QuarkusTransaction
import io.quarkus.test.junit.QuarkusTest
import io.restassured.RestAssured.given
import org.hamcrest.Matchers.equalTo
import org.hamcrest.Matchers.hasItem
import org.hamcrest.Matchers.hasSize
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.time.LocalDate

@QuarkusTest
class DataroomResourceTest {

    private fun fact(
        dataroom: String,
        tier: String,
        factType: String,
        sourceDoc: String,
        docType: String = "bank_statement",
        valuePence: Long? = null,
        periodStart: LocalDate? = null,
        confidence: Float = 0.99f,
    ) = Fact().apply {
        this.dataroom = dataroom
        this.tier = tier
        this.docType = docType
        this.factType = factType
        this.sourceDoc = sourceDoc
        this.valuePence = valuePence
        this.periodStart = periodStart
        this.periodEnd = periodStart?.plusMonths(1)?.minusDays(1)
        this.page = 1
        this.confidence = confidence
    }

    @BeforeEach
    fun seed() {
        QuarkusTransaction.requiringNew().run {
            Fact.deleteAll()
            // "alpha" is the thin real room from the Python report run:
            // 1 bank month, 1 VAT quarter, no accounts, no mgmt P&L, a
            // lease — the case that scored 23/100 in report/sufficiency.py.
            Fact.persist(
                fact(
                    "alpha", "real", "bank_closing_balance",
                    "financials/March 25 statement.pdf",
                    valuePence = 60_269_09,
                    periodStart = LocalDate.of(2025, 3, 1),
                ),
                fact(
                    "alpha", "real", "bank_txn",
                    "financials/March 25 statement.pdf",
                    valuePence = 2_166_67,
                    periodStart = LocalDate.of(2025, 3, 1),
                    confidence = 0.65f, // below threshold -> needs review
                ),
                fact(
                    "alpha", "real", "vat_box6",
                    "financials/Q1 25 return.pdf", docType = "vat_return",
                    valuePence = 98_915_00,
                    periodStart = LocalDate.of(2025, 1, 1),
                ),
                fact(
                    "alpha", "real", "lease_annual_rent",
                    "property/lease.pdf", docType = "lease",
                    valuePence = 26_000_00,
                ),
                // second room so list() has to group correctly
                fact(
                    "beta", "ground_truth", "mgmt_revenue",
                    "management_pnl.pdf", docType = "management_pnl",
                    valuePence = 41_000_00,
                    periodStart = LocalDate.of(2024, 4, 1),
                ),
            )
        }
    }

    @Test
    fun `list groups by dataroom and tier with counts`() {
        given()
            .`when`().get("/api/v1/datarooms")
            .then()
            .statusCode(200)
            .body("", hasSize<Any>(2))
            .body("[0].dataroom", equalTo("alpha"))
            .body("[0].tier", equalTo("real"))
            .body("[0].facts", equalTo(4))
            .body("[0].documents", equalTo(3))
            .body("[0].needsReview", equalTo(1))
            .body("[1].dataroom", equalTo("beta"))
    }

    @Test
    fun `facts returns provenance and honours filters`() {
        given()
            .`when`().get("/api/v1/datarooms/alpha/facts?tier=real")
            .then()
            .statusCode(200)
            .body("", hasSize<Any>(4))
            // ordered by period_start with NULLS LAST — same as Python's
            // fetch_facts: VAT (Jan) first, lease (null period) last
            .body("[0].sourceDoc", equalTo("financials/Q1 25 return.pdf"))
            .body("[3].sourceDoc", equalTo("property/lease.pdf"))
            .body("[0].page", equalTo(1))
            .body("[0].confidence", equalTo(0.99f))

        given()
            .`when`().get("/api/v1/datarooms/alpha/facts?tier=real&factType=vat_box6")
            .then()
            .statusCode(200)
            .body("", hasSize<Any>(1))
            .body("[0].valuePence", equalTo(9891500))

        // minConfidence excludes the quarantined 0.65 transaction
        given()
            .`when`().get("/api/v1/datarooms/alpha/facts?tier=real&minConfidence=0.8")
            .then()
            .statusCode(200)
            .body("", hasSize<Any>(3))

        given()
            .`when`().get("/api/v1/datarooms/alpha/facts")
            .then()
            .statusCode(400)
    }

    @Test
    fun `sufficiency reproduces the Python 23-of-100 thin-room case`() {
        // Cross-language pin: identical inputs scored 23/100 by
        // src/diligence/report/sufficiency.py on the real ingest run.
        given()
            .`when`().get("/api/v1/datarooms/alpha/sufficiency?tier=real")
            .then()
            .statusCode(200)
            .body("score", equalTo(23))
            .body("items", hasSize<Any>(5))
            .body("gaps", hasItem("Bank statements (months): 1 of 24 present"))
            .body("gaps", hasItem("VAT returns (quarters): 1 of 8 present"))
            .body("gaps", hasItem("Statutory accounts (years): 0 of 2 present"))
            .body("gaps", hasItem("Management P&L (months): 0 of 24 present"))
            .body(
                "gaps", hasItem(
                    "1 extracted figures were too unclear to use and need " +
                        "human verification",
                ),
            )
            .body("needsReview", equalTo(1))
    }

    @Test
    fun `sufficiency expectations are overridable per room config`() {
        // A room whose config only expects 1 month / 1 quarter / 0 FYs:
        // ratios 1, 1, 1, 0 (mgmt 0/1), 1 -> 80.
        given()
            .`when`()
            .get(
                "/api/v1/datarooms/alpha/sufficiency" +
                    "?tier=real&bankMonths=1&vatQuarters=1&fys=0",
            )
            .then()
            .statusCode(200)
            .body("score", equalTo(80))
    }

    @Test
    fun `sufficiency 404s for an unknown dataroom`() {
        given()
            .`when`().get("/api/v1/datarooms/nope/sufficiency?tier=real")
            .then()
            .statusCode(404)
    }

    @Test
    fun `health endpoint is live`() {
        given().`when`().get("/q/health").then().statusCode(200)
    }
}
