package diligence.api.fact

import io.quarkus.panache.common.Parameters
import io.quarkus.panache.common.Sort
import jakarta.persistence.EntityManager
import jakarta.ws.rs.GET
import jakarta.ws.rs.NotFoundException
import jakarta.ws.rs.Path
import jakarta.ws.rs.PathParam
import jakarta.ws.rs.Produces
import jakarta.ws.rs.QueryParam
import jakarta.ws.rs.core.MediaType

/**
 * Read-only views over the fact table. Deterministic code computing over
 * facts (golden rule 1) — no model calls anywhere in this service.
 */
@Path("/api/v1/datarooms")
@Produces(MediaType.APPLICATION_JSON)
class DataroomResource(private val em: EntityManager) {

    @GET
    fun list(): List<DataroomSummary> {
        @Suppress("UNCHECKED_CAST")
        val rows = em.createNativeQuery(
            """
            SELECT dataroom, tier, COUNT(*) AS facts,
                   COUNT(DISTINCT source_doc) AS documents,
                   COUNT(*) FILTER (WHERE confidence < :threshold
                                    AND NOT jsonb_exists(attrs, 'reviewed'))
                       AS needs_review
            FROM fact
            GROUP BY dataroom, tier
            ORDER BY dataroom, tier
            """,
        ).setParameter("threshold", CONFIDENCE_REVIEW_THRESHOLD)
            .resultList as List<Array<Any?>>
        return rows.map {
            DataroomSummary(
                dataroom = it[0] as String,
                tier = it[1] as String,
                facts = (it[2] as Number).toLong(),
                documents = (it[3] as Number).toLong(),
                needsReview = (it[4] as Number).toLong(),
            )
        }
    }

    /** Mirrors fetch_facts() in src/diligence/facts/db.py, provenance included. */
    @GET
    @Path("/{dataroom}/facts")
    fun facts(
        @PathParam("dataroom") dataroom: String,
        @QueryParam("tier") tier: String?,
        @QueryParam("factType") factType: String?,
        @QueryParam("minConfidence") minConfidence: Float?,
    ): List<FactDto> {
        val t = tier ?: throw jakarta.ws.rs.BadRequestException("tier is required")
        var query = "dataroom = :dataroom and tier = :tier and confidence >= :min"
        val params = Parameters.with("dataroom", dataroom)
            .and("tier", t)
            .and("min", minConfidence ?: 0f)
        if (factType != null) {
            query += " and factType = :factType"
            params.and("factType", factType)
        }
        val sort = Sort.by("periodStart").and("sourceDoc").and("page").and("id")
        return Fact.find(query, sort, params).list().map { FactDto.from(it) }
    }

    /**
     * Faithful port of assess() in src/diligence/report/sufficiency.py.
     * Defaults are the real-room DD standard (24 months / 8 quarters /
     * 2 FYs); synthetic rooms pass their config-derived expectations.
     */
    @GET
    @Path("/{dataroom}/sufficiency")
    fun sufficiency(
        @PathParam("dataroom") dataroom: String,
        @QueryParam("tier") tier: String?,
        @QueryParam("bankMonths") bankMonths: Int?,
        @QueryParam("vatQuarters") vatQuarters: Int?,
        @QueryParam("fys") fys: Int?,
    ): SufficiencyReport {
        val t = tier ?: throw jakarta.ws.rs.BadRequestException("tier is required")
        if (Fact.count("dataroom = ?1 and tier = ?2", dataroom, t) == 0L) {
            throw NotFoundException("No facts for $dataroom/$t")
        }

        fun distinctDocs(factType: String): Int = em.createQuery(
            "select count(distinct f.sourceDoc) from Fact f where " +
                "f.dataroom = :d and f.tier = :t and f.factType = :ft",
            java.lang.Long::class.java,
        ).setParameter("d", dataroom).setParameter("t", t)
            .setParameter("ft", factType).singleResult.toInt()

        val mgmtMonths = em.createQuery(
            "select count(distinct f.periodStart) from Fact f where " +
                "f.dataroom = :d and f.tier = :t and f.factType = 'mgmt_revenue'",
            java.lang.Long::class.java,
        ).setParameter("d", dataroom).setParameter("t", t).singleResult.toInt()

        val needsReview = (
            em.createNativeQuery(
                """
                SELECT COUNT(*) FROM fact
                WHERE dataroom = :d AND tier = :t AND confidence < :threshold
                  AND NOT jsonb_exists(attrs, 'reviewed')
                """,
            ).setParameter("d", dataroom).setParameter("t", t)
                .setParameter("threshold", CONFIDENCE_REVIEW_THRESHOLD)
                .singleResult as Number
            ).toLong()

        val expectedBankMonths = bankMonths ?: 24
        val lease = if (Fact.count(
                "dataroom = ?1 and tier = ?2 and factType = 'lease_annual_rent'",
                dataroom, t,
            ) > 0
        ) 1 else 0

        // Presence marker for statutory accounts is a balance-sheet line:
        // small companies legally file without a P&L (same rationale as the
        // Python implementation — learned from a real CH filing).
        return SufficiencyReport(
            items = listOf(
                SufficiencyItem(
                    "Bank statements (months)",
                    distinctDocs("bank_closing_balance"), expectedBankMonths,
                ),
                SufficiencyItem(
                    "VAT returns (quarters)",
                    distinctDocs("vat_box6"), vatQuarters ?: 8,
                ),
                SufficiencyItem(
                    "Statutory accounts (years)",
                    distinctDocs("stat_net_assets"), fys ?: 2,
                ),
                SufficiencyItem(
                    "Management P&L (months)", mgmtMonths, expectedBankMonths,
                ),
                SufficiencyItem("Lease", lease, 1),
            ),
            needsReview = needsReview,
        )
    }
}
