package com.assistant

import java.io.File
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 后端联动启动:打开 PyCharm 时,若后端尚未运行则用 pythonw 静默拉起(无窗口)。
 * 日志写入 <backendDir>/backend-autostart.log,方便排查。
 */
object BackendStarter {
    private val starting = AtomicBoolean(false)

    fun ensureStarted() {
        val s = AssistantSettings.getInstance().state
        if (!s.autoStartBackend) return
        if (s.backendDir.isBlank()) return
        if (isReachable(s.backendUrl)) return
        if (!starting.compareAndSet(false, true)) return
        try {
            spawn(s)
        } finally {
            starting.set(false)
        }
    }

    private fun isReachable(url: String): Boolean {
        return try {
            val req = HttpRequest.newBuilder(URI.create(url.trimEnd('/') + "/health"))
                .timeout(Duration.ofSeconds(2))
                .GET()
                .build()
            val http = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(2))
                .build()
            http.send(req, HttpResponse.BodyHandlers.ofString()).statusCode() == 200
        } catch (_: Exception) {
            false
        }
    }

    private fun spawn(s: AssistantSettings.State) {
        val dir = File(s.backendDir)
        if (!dir.isDirectory) return
        val logFile = File(dir, "backend-autostart.log")
        try {
            ProcessBuilder(resolvePython(s.pythonPath), "-m", "backend.main")
                .directory(dir)
                .redirectErrorStream(true)
                .redirectOutput(ProcessBuilder.Redirect.appendTo(logFile))
                .start()
        } catch (_: Exception) {
            // 忽略启动失败;用户仍可手动双击脚本启动
        }
    }

    private fun resolvePython(explicit: String): String {
        if (explicit.isNotBlank()) return explicit
        for (c in listOf("D:\\AI\\pythonw.exe", "D:\\AI\\python.exe")) {
            if (File(c).exists()) return c
        }
        return "pythonw" // 兜底:靠系统 PATH 解析
    }
}
