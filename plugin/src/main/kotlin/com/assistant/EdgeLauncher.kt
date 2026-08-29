package com.assistant

import com.intellij.openapi.ui.Messages
import java.awt.Desktop
import java.io.File
import java.net.URI
import java.net.URLEncoder

object EdgeLauncher {

    private fun env(name: String): String = System.getenv(name) ?: ""

    private val edgeCandidates = listOf(
        env("ProgramFiles(x86)") + "\\Microsoft\\Edge\\Application\\msedge.exe",
        env("ProgramFiles") + "\\Microsoft\\Edge\\Application\\msedge.exe",
        env("LOCALAPPDATA") + "\\Microsoft\\Edge\\Application\\msedge.exe",
        "msedge.exe", // 最后尝试从 PATH 查找
    )

    fun search(query: String) {
        val keyword = query.trim()
        if (keyword.isEmpty()) return
        val url = AssistantSettings.getInstance().state.searchUrl + URLEncoder.encode(keyword, "UTF-8")
        try {
            val edge = edgeCandidates.firstOrNull { it == "msedge.exe" || File(it).exists() }
            if (edge != null) {
                try {
                    ProcessBuilder(edge, "--new-window", url).start()
                    return
                } catch (_: Exception) {
                    // 启动 Edge 失败,回退到默认浏览器
                }
            }
            Desktop.getDesktop().browse(URI(url))
        } catch (e: Exception) {
            Messages.showErrorDialog("无法打开浏览器:${e.message}", "错误")
        }
    }
}
