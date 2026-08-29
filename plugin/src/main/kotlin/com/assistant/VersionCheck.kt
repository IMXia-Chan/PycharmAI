package com.assistant

import com.intellij.ide.BrowserUtil
import com.intellij.ide.plugins.PluginManagerCore
import com.intellij.notification.NotificationAction
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.extensions.PluginId
import com.intellij.openapi.project.Project

/**
 * 插件新版本检查(方案 A):
 * 打开项目后,在后台问云端「最新版本是多少」,比当前插件版本新就弹一个通知,
 * 附「打开下载页」按钮(链接来自云端 latest.json,管理员可随时改)。
 */
object VersionCheck {

    private const val PLUGIN_ID = "com.assistant.python-assistant"

    /** 当前插件版本,直接从构建信息读取,和 build.gradle.kts 的 version 保持一致。 */
    private fun currentVersion(): String =
        try {
            PluginManagerCore.getPlugin(PluginId.getId(PLUGIN_ID))?.version ?: "0.0.0"
        } catch (e: Exception) {
            "0.0.0"
        }

    /** 后台检查(重试几次,给后端留启动时间)。 */
    fun check(project: Project) {
        Thread {
            var info = VersionInfo("", "", "")
            for (i in 0 until 4) {
                if (i > 0) Thread.sleep(3000)
                info = try {
                    BackendClient.latestVersion()
                } catch (e: Exception) {
                    VersionInfo("", "", "")
                }
                if (info.version.isNotBlank()) break
            }
            val latest = info.version.trim()
            if (latest.isNotEmpty() && isNewer(latest, currentVersion())) {
                ApplicationManager.getApplication().invokeLater {
                    notifyUpdate(project, latest, currentVersion(), info.message, info.url)
                }
            }
        }.start()
    }

    /** 按「点分版本号」数值比较,避免 "1.10.0" 被当成小于 "1.9.0"。 */
    private fun isNewer(latest: String, current: String): Boolean {
        val a = latest.split('.')
        val b = current.split('.')
        val n = maxOf(a.size, b.size)
        for (i in 0 until n) {
            val x = a.getOrNull(i)?.trim()?.toIntOrNull() ?: 0
            val y = b.getOrNull(i)?.trim()?.toIntOrNull() ?: 0
            if (x != y) return x > y
        }
        return false
    }

    private fun notifyUpdate(project: Project, latest: String, current: String, message: String, url: String) {
        val content = if (message.isBlank()) {
            "发现新版本 v$latest(当前 v$current)。"
        } else {
            "发现新版本 v$latest(当前 v$current):$message"
        }
        val group = NotificationGroupManager.getInstance().getNotificationGroup("PythonAssistant.Notifications")
        val n = group.createNotification("Python 代码助手", content, NotificationType.INFORMATION)
        if (url.isNotBlank()) {
            n.addAction(NotificationAction.createSimple("打开下载页", Runnable { BrowserUtil.browse(url) }))
        }
        n.notify(project)
    }
}
