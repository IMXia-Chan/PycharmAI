package com.assistant

import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets
import java.time.Duration
import java.util.Base64

data class Issue(
    val category: String,
    val title: String,
    val message: String,
    val suggestion: String,
    val severity: String,
    val line: Int = 0,
)

data class Candidate(
    val name: String,
    val signature: String,
    val module: String,
    val description: String,
)

data class CompareResult(val summary: String, val differences: List<Map<String, String>>)

data class Note(val title: String, val content: String, val createdAt: String)

data class Record(
    val category: String,
    val title: String,
    val message: String,
    val filename: String,
    val line: Int,
    val code: String,
    val severity: String,
)

data class Snippet(
    val id: String,
    val title: String,
    val code: String,
    val note: String,
    val createdAt: String,
)

data class AdminLoginResult(val ok: Boolean, val ticket: String, val email: String, val error: String)

data class AdminVerifyResult(val ok: Boolean, val sessionToken: String, val error: String)

data class VerifyResult(val ok: Boolean, val error: String)

data class VersionInfo(val version: String, val message: String, val url: String)

object BackendClient {
    private val gson = Gson()
    private val http = HttpClient.newBuilder()
        .version(HttpClient.Version.HTTP_1_1)
        .connectTimeout(Duration.ofSeconds(5))
        .build()

    private fun base(): String = AssistantSettings.getInstance().state.backendUrl.trimEnd('/')

    /** 给每个请求附加 API key 与多用户身份头(插件本机设置)。 */
    private fun applyHeaders(b: HttpRequest.Builder): HttpRequest.Builder {
        val s = AssistantSettings.getInstance().state
        b.header("Content-Type", "application/json")
        if (s.apiKey.isNotBlank()) b.header("X-API-Key", s.apiKey)
        // 用户名/令牌可能是中文,直接放进 HTTP header 会让 Java HttpClient 抛异常,故 Base64 编码
        if (s.username.isNotBlank()) b.header("X-Username", base64(s.username))
        if (s.token.isNotBlank()) b.header("X-Token", base64(s.token))
        return b
    }

    private fun base64(s: String): String =
        Base64.getEncoder().encodeToString(s.toByteArray(StandardCharsets.UTF_8))

    private fun post(path: String, payload: JsonObject, timeoutSeconds: Long = 60): String {
        val req = applyHeaders(HttpRequest.newBuilder(URI.create(base() + path)))
            .timeout(Duration.ofSeconds(timeoutSeconds))
            .POST(HttpRequest.BodyPublishers.ofString(gson.toJson(payload)))
            .build()
        return http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)).body()
    }

    private fun get(path: String): String {
        val req = applyHeaders(HttpRequest.newBuilder(URI.create(base() + path)))
            .timeout(Duration.ofSeconds(30))
            .GET()
            .build()
        return http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)).body()
    }

    private fun delete(path: String): String {
        val req = applyHeaders(HttpRequest.newBuilder(URI.create(base() + path)))
            .timeout(Duration.ofSeconds(30))
            .DELETE()
            .build()
        return http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)).body()
    }

    fun analyze(code: String, line: Int): List<Issue> {
        val payload = JsonObject()
        payload.addProperty("code", code)
        payload.addProperty("line", line)
        val root = JsonParser.parseString(post("/api/analyze?deep=true", payload)).asJsonObject
        val arr = root.getAsJsonArray("issues") ?: return emptyList()
        return arr.map {
            val o = it.asJsonObject
            Issue(o.str("category"), o.str("title"), o.str("message"), o.str("suggestion"), o.str("severity"), o.int("line"))
        }
    }

    fun searchFunctions(query: String): List<Candidate> {
        val payload = JsonObject()
        payload.addProperty("code", query)
        val root = JsonParser.parseString(post("/api/search-functions", payload)).asJsonObject
        val arr = root.getAsJsonArray("candidates") ?: return emptyList()
        return arr.map {
            val o = it.asJsonObject
            Candidate(o.str("name"), o.str("signature"), o.str("module"), o.str("description"))
        }
    }

    fun compare(a: String, b: String): CompareResult {
        val payload = JsonObject()
        payload.addProperty("function_a", a)
        payload.addProperty("function_b", b)
        val root = JsonParser.parseString(post("/api/compare", payload)).asJsonObject
        val summary = root.str("summary")
        val diffs = mutableListOf<Map<String, String>>()
        root.getAsJsonArray("differences")?.forEach {
            val o = it.asJsonObject
            diffs.add(
                mapOf(
                    "dimension" to o.str("dimension"),
                    "a" to o.str("a"),
                    "b" to o.str("b"),
                    "note" to o.str("note"),
                )
            )
        }
        return CompareResult(summary, diffs)
    }

    /** 中文问答:直接问 Python 问题,返回 AI 的文本回答。 */
    fun chat(question: String): String {
        val payload = JsonObject()
        payload.addProperty("question", question)
        val root = JsonParser.parseString(post("/api/chat", payload)).asJsonObject
        return root.str("reply")
    }

    /** 用中文解释一段代码在做什么。 */
    fun explain(code: String): String {
        val payload = JsonObject()
        payload.addProperty("code", code)
        return JsonParser.parseString(post("/api/explain", payload)).asJsonObject.str("text")
    }

    /** 为一段代码加中文注释,返回加注释后的完整代码。 */
    fun comment(code: String): String {
        val payload = JsonObject()
        payload.addProperty("code", code)
        return JsonParser.parseString(post("/api/comment", payload)).asJsonObject.str("code")
    }

    /** 解释一段运行时报错。 */
    fun explainError(error: String): String {
        val payload = JsonObject()
        payload.addProperty("text", error)
        return JsonParser.parseString(post("/api/explain-error", payload)).asJsonObject.str("text")
    }

    /** 自动修复代码,返回修复后的完整代码。 */
    fun fix(code: String): String {
        val payload = JsonObject()
        payload.addProperty("code", code)
        return JsonParser.parseString(post("/api/fix", payload)).asJsonObject.str("code")
    }

    fun notes(): List<Note> {
        val el = JsonParser.parseString(get("/api/notes"))
        if (!el.isJsonArray) return emptyList()
        return el.asJsonArray.map {
            val o = it.asJsonObject
            Note(o.str("title"), o.str("content"), o.str("created_at"))
        }
    }

    fun snippets(): List<Snippet> {
        val el = JsonParser.parseString(get("/api/snippets"))
        if (!el.isJsonArray) return emptyList()
        return el.asJsonArray.map {
            val o = it.asJsonObject
            Snippet(o.str("id"), o.str("title"), o.str("code"), o.str("note"), o.str("created_at"))
        }
    }

    fun addSnippet(title: String, code: String, note: String): Snippet {
        val payload = JsonObject()
        payload.addProperty("title", title)
        payload.addProperty("code", code)
        payload.addProperty("note", note)
        val o = JsonParser.parseString(post("/api/snippets", payload)).asJsonObject
        return Snippet(o.str("id"), o.str("title"), o.str("code"), o.str("note"), o.str("created_at"))
    }

    fun deleteSnippet(id: String) {
        delete("/api/snippets/$id")
    }

    fun records(): List<Record> {
        val el = JsonParser.parseString(get("/api/records"))
        if (!el.isJsonArray) return emptyList()
        return el.asJsonArray.map {
            val o = it.asJsonObject
            Record(
                o.str("category"), o.str("title"), o.str("message"),
                o.str("filename"), o.int("line"), o.str("code"), o.str("severity"),
            )
        }
    }

    fun generateNote(): Note {
        val root = JsonParser.parseString(post("/api/notes/generate", JsonObject())).asJsonObject
        return Note(root.str("title"), root.str("content"), root.str("created_at"))
    }

    /** 查询云端的最新插件版本(失败返回空,不抛异常)。 */
    fun latestVersion(): VersionInfo {
        return try {
            val root = JsonParser.parseString(get("/api/version")).asJsonObject
            VersionInfo(root.str("version"), root.str("message"), root.str("url"))
        } catch (e: Exception) {
            VersionInfo("", "", "")
        }
    }

    /** 后端是否可达(调 /health,成功返回 true)。 */
    fun healthOk(): Boolean {
        return try {
            get("/health").isNotBlank()
        } catch (_: Exception) {
            false
        }
    }

    /** 申请一个网页入口令牌(只有拿到令牌才能打开 /web)。失败返回空串。 */
    fun openWeb(): String {
        return try {
            JsonParser.parseString(get("/api/web/open")).asJsonObject.str("token")
        } catch (_: Exception) {
            ""
        }
    }

    /** 校验当前 API key 是否有效(调 /api/verify)。 */
    fun verifyKey(): VerifyResult {
        return try {
            val root = JsonParser.parseString(post("/api/verify", JsonObject())).asJsonObject
            VerifyResult(root.bool("ok"), root.str("error"))
        } catch (e: Exception) {
            VerifyResult(false, e.message ?: "后端不可达")
        }
    }

    fun record(code: String, filename: String, line: Int, title: String, category: String, severity: String, message: String = "") {
        val payload = JsonObject()
        payload.addProperty("code", code)
        payload.addProperty("filename", filename)
        payload.addProperty("line", line)
        payload.addProperty("title", title)
        payload.addProperty("category", category)
        payload.addProperty("severity", severity)
        payload.addProperty("message", message)
        post("/api/record", payload)
    }

    /** 候选库一键上传:把选中的本地记录批量发到网页端记录库(保留 filename,网页按文件名分组)。 */
    fun uploadRecords(records: List<Record>) {
        val payload = JsonObject()
        val arr = JsonArray()
        records.forEach { r ->
            val o = JsonObject()
            o.addProperty("code", r.code)
            o.addProperty("filename", r.filename)
            o.addProperty("line", r.line)
            o.addProperty("title", r.title)
            o.addProperty("message", r.message)
            o.addProperty("category", r.category)
            o.addProperty("severity", r.severity)
            arr.add(o)
        }
        payload.add("records", arr)
        post("/api/records/upload", payload)
    }

    /** 管理员登录第一步:校验用户名+密码,服务器发邮箱验证码,返回 ticket。 */
    fun adminLogin(username: String, password: String): AdminLoginResult {
        val payload = JsonObject()
        payload.addProperty("username", username)
        payload.addProperty("password", password)
        val root = JsonParser.parseString(post("/api/admin/login", payload)).asJsonObject
        return AdminLoginResult(root.bool("ok"), root.str("ticket"), root.str("email"), root.str("error"))
    }

    /** 管理员登录第二步:校验邮箱验证码,返回会话 token。 */
    fun adminVerify(ticket: String, code: String): AdminVerifyResult {
        val payload = JsonObject()
        payload.addProperty("ticket", ticket)
        payload.addProperty("code", code)
        val root = JsonParser.parseString(post("/api/admin/verify", payload)).asJsonObject
        return AdminVerifyResult(root.bool("ok"), root.str("session_token"), root.str("error"))
    }

    private fun JsonObject.str(key: String): String =
        if (has(key) && !get(key).isJsonNull) get(key).asString else ""

    private fun JsonObject.int(key: String): Int =
        if (has(key) && !get(key).isJsonNull) get(key).asInt else 0

    private fun JsonObject.bool(key: String): Boolean =
        has(key) && !get(key).isJsonNull && get(key).asBoolean
}
