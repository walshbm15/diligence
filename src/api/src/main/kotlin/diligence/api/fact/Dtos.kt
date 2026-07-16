package diligence.api.fact

import com.fasterxml.jackson.databind.JsonNode
import java.time.LocalDate

/** One dataroom/tier in the fact table, with enough counts to triage. */
data class DataroomSummary(
    val dataroom: String,
    val tier: String,
    val facts: Long,
    val documents: Long,
    val needsReview: Long,
)

/** A fact with its full provenance — no fact leaves this API without it. */
data class FactDto(
    val id: Long,
    val dataroom: String,
    val tier: String,
    val docType: String,
    val factType: String,
    val valuePence: Long?,
    val valueNum: Double?,
    val valueText: String?,
    val valueDate: LocalDate?,
    val periodStart: LocalDate?,
    val periodEnd: LocalDate?,
    val attrs: JsonNode,
    val sourceDoc: String,
    val page: Int,
    val bbox: JsonNode?,
    val confidence: Float,
    val extractor: String,
) {
    companion object {
        fun from(f: Fact) = FactDto(
            id = f.id!!,
            dataroom = f.dataroom,
            tier = f.tier,
            docType = f.docType,
            factType = f.factType,
            valuePence = f.valuePence,
            valueNum = f.valueNum,
            valueText = f.valueText,
            valueDate = f.valueDate,
            periodStart = f.periodStart,
            periodEnd = f.periodEnd,
            attrs = f.attrs,
            sourceDoc = f.sourceDoc,
            page = f.page,
            bbox = f.bbox,
            confidence = f.confidence,
            extractor = f.extractor,
        )
    }
}

/** Faithful port of SufficiencyItem in src/diligence/report/sufficiency.py. */
data class SufficiencyItem(
    val label: String,
    val have: Int,
    val want: Int,
) {
    val ratio: Double
        get() = if (want == 0) 1.0 else minOf(1.0, have.toDouble() / want)
    val complete: Boolean
        get() = have >= want
}

/** Faithful port of SufficiencyReport: same score arithmetic, same gap text. */
data class SufficiencyReport(
    val items: List<SufficiencyItem>,
    val needsReview: Long,
) {
    val score: Int
        get() = Math.round(100 * items.sumOf { it.ratio } / items.size).toInt()

    val gaps: List<String>
        get() {
            val out = items.filterNot { it.complete }
                .map { "${it.label}: ${it.have} of ${it.want} present" }
                .toMutableList()
            if (needsReview > 0) {
                out += "$needsReview extracted figures were too unclear to " +
                    "use and need human verification"
            }
            return out
        }
}
