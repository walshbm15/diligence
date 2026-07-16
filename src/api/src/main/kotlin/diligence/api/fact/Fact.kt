package diligence.api.fact

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.node.JsonNodeFactory
import io.quarkus.hibernate.orm.panache.kotlin.PanacheCompanionBase
import io.quarkus.hibernate.orm.panache.kotlin.PanacheEntityBase
import jakarta.persistence.Column
import jakarta.persistence.Entity
import jakarta.persistence.GeneratedValue
import jakarta.persistence.GenerationType
import jakarta.persistence.Id
import jakarta.persistence.Table
import org.hibernate.annotations.JdbcTypeCode
import org.hibernate.type.SqlTypes
import java.time.LocalDate
import java.time.OffsetDateTime

/** Extracted figures below this are quarantined for human review — must
 *  stay equal to CONFIDENCE_REVIEW_THRESHOLD in src/diligence/facts/model.py. */
const val CONFIDENCE_REVIEW_THRESHOLD = 0.8f

/**
 * Read-side mapping of the fact table. The Python pipeline
 * (src/diligence/facts) owns this schema and all production writes until
 * issue #29; this service treats it as read-only outside of tests.
 * Provenance columns (source_doc, page, confidence) are NOT NULL by
 * design — golden rule 2.
 */
@Entity
@Table(name = "fact")
class Fact : PanacheEntityBase {
    companion object : PanacheCompanionBase<Fact, Long>

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(nullable = false)
    lateinit var dataroom: String

    @Column(nullable = false)
    lateinit var tier: String

    @Column(name = "doc_type", nullable = false)
    lateinit var docType: String

    @Column(name = "fact_type", nullable = false)
    lateinit var factType: String

    @Column(name = "value_pence")
    var valuePence: Long? = null

    @Column(name = "value_num")
    var valueNum: Double? = null

    @Column(name = "value_text")
    var valueText: String? = null

    @Column(name = "value_date")
    var valueDate: LocalDate? = null

    @Column(name = "period_start")
    var periodStart: LocalDate? = null

    @Column(name = "period_end")
    var periodEnd: LocalDate? = null

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false)
    var attrs: JsonNode = JsonNodeFactory.instance.objectNode()

    @Column(name = "source_doc", nullable = false)
    lateinit var sourceDoc: String

    @Column(nullable = false)
    var page: Int = 1

    @JdbcTypeCode(SqlTypes.JSON)
    var bbox: JsonNode? = null

    @Column(nullable = false)
    var confidence: Float = 0f

    @Column(nullable = false)
    var extractor: String = ""

    @Column(name = "created_at", insertable = false, updatable = false)
    var createdAt: OffsetDateTime? = null

    val needsReview: Boolean
        get() = confidence < CONFIDENCE_REVIEW_THRESHOLD && !attrs.has("reviewed")
}
