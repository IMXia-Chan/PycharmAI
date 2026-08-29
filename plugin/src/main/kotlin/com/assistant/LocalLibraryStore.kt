package com.assistant

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.File
import java.time.LocalDateTime
import java.util.UUID

/** 一条本地记录:报错记录 / 代码解释 / 报错解释。 */
data class LocalRecord(
    val id: String,
    val kind: String,          // "record"=报错记录 | "explain"=代码解释 | "error-explain"=报错解释
    val title: String,
    val code: String,
    val message: String,
    val filename: String,      // 源代码文件名(报错解释用固定组名「报错解释」)
    val line: Int,
    val category: String,
    val severity: String,
    val createdAt: String,
)

/** 本地库整体数据:记录 + 唯一候选库(暂存要上传的 record id)。 */
data class LocalStore(
    val records: List<LocalRecord> = emptyList(),
    val candidateIds: List<String> = emptyList(),
)

/** 插件本机的文件库存储:JSON 文件,手写序列化(不用 Gson 反射,避免 final 字段问题)。 */
object LocalLibraryStore {

    private const val DIR = ".python-assistant"
    private const val FILE = "library.json"
    private val lock = Any()

    private fun file(): File = File(File(System.getProperty("user.home"), DIR), FILE)

    private fun now(): String = LocalDateTime.now().toString()

    // ---------- 读写 ----------

    private fun load(): LocalStore = synchronized(lock) {
        val f = file()
        if (!f.exists()) return@synchronized LocalStore()
        try {
            val root = JsonParser.parseString(f.readText(Charsets.UTF_8)).asJsonObject
            val records = mutableListOf<LocalRecord>()
            if (root.has("records") && root.get("records").isJsonArray) {
                root.getAsJsonArray("records").forEach {
                    val o = it.asJsonObject
                    records.add(
                        LocalRecord(
                            id = o.str("id"), kind = o.str("kind"),
                            title = o.str("title"), code = o.str("code"), message = o.str("message"),
                            filename = o.str("filename"), line = o.int("line"),
                            category = o.str("category"), severity = o.str("severity"),
                            createdAt = o.str("createdAt"),
                        )
                    )
                }
            }
            val candidateIds = mutableListOf<String>()
            if (root.has("candidateIds") && root.get("candidateIds").isJsonArray) {
                root.getAsJsonArray("candidateIds").forEach { candidateIds.add(it.asString) }
            }
            LocalStore(records, candidateIds)
        } catch (_: Exception) {
            LocalStore()
        }
    }

    private fun save(store: LocalStore) = synchronized(lock) {
        val root = JsonObject()
        val recs = JsonArray()
        store.records.forEach { r ->
            val o = JsonObject()
            o.addProperty("id", r.id); o.addProperty("kind", r.kind)
            o.addProperty("title", r.title); o.addProperty("code", r.code)
            o.addProperty("message", r.message); o.addProperty("filename", r.filename)
            o.addProperty("line", r.line); o.addProperty("category", r.category)
            o.addProperty("severity", r.severity); o.addProperty("createdAt", r.createdAt)
            recs.add(o)
        }
        root.add("records", recs)
        val ids = JsonArray()
        store.candidateIds.forEach { ids.add(it) }
        root.add("candidateIds", ids)
        val f = file()
        f.parentFile?.mkdirs()
        f.writeText(root.toString(), Charsets.UTF_8)
    }

    // ---------- 记录 ----------

    fun addRecord(
        kind: String, title: String, code: String, message: String,
        filename: String, line: Int, category: String, severity: String,
    ): LocalRecord {
        val store = load()
        val rec = LocalRecord(
            id = UUID.randomUUID().toString().replace("-", ""),
            kind = kind, title = title, code = code, message = message,
            filename = filename.ifBlank { "未命名文件" }, line = line,
            category = category, severity = severity, createdAt = now(),
        )
        save(store.copy(records = store.records + rec))
        return rec
    }

    fun deleteRecord(id: String) {
        val store = load()
        save(
            store.copy(
                records = store.records.filter { it.id != id },
                candidateIds = store.candidateIds.filter { it != id },
            )
        )
    }

    fun records(): List<LocalRecord> = load().records

    // ---------- 候选库(唯一,临时) ----------

    fun addToCandidate(ids: List<String>) {
        val store = load()
        save(store.copy(candidateIds = (store.candidateIds + ids).distinct()))
    }

    fun removeFromCandidate(id: String) {
        val store = load()
        save(store.copy(candidateIds = store.candidateIds.filter { it != id }))
    }

    fun candidateRecords(): List<LocalRecord> {
        val store = load()
        val byId = store.records.associateBy { it.id }
        return store.candidateIds.mapNotNull { byId[it] }
    }

    fun clearCandidate() {
        val store = load()
        save(store.copy(candidateIds = emptyList()))
    }

    // ---------- 小工具 ----------

    private fun JsonObject.str(key: String): String =
        if (has(key) && !get(key).isJsonNull) get(key).asString else ""

    private fun JsonObject.int(key: String): Int =
        if (has(key) && !get(key).isJsonNull) get(key).asInt else 0
}
