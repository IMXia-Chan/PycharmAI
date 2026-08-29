package com.assistant

import com.intellij.notification.NotificationAction
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project

/**
 * 启动自检:插件加载时自动检查「后端是否可达 + API key 是否有效」,
 * 然后用一条通知明确告知结果——成功则「检查完毕,可以启动」,失败则点出具体哪里坏了。
 */
object SelfCheck {

    fun run(project: Project) {
        Thread {
            val backendUp = waitUntil(10, 1000L) { BackendClient.healthOk() }
            val result = when {
                !backendUp -> Result(
                    false, "后端未启动",
                    "请确认本地后端服务已运行;或在「接入你的 API」里勾选「打开 PyCharm 时自动启动后端」",
                )
                else -> {
                    val v = BackendClient.verifyKey()
                    if (v.ok) Result(true, "检查完毕，可以启动", "后端正常、API key 有效")
                    else Result(false, "API key 无效", v.error.ifBlank { "请在「接入你的 API」里填有效的 DeepSeek API key" })
                }
            }
            notify(project, result)
        }.start()
    }

    /** 轮询 [cond],最多 [maxTries] 次、每次间隔 [delayMs] 毫秒。 */
    private fun waitUntil(maxTries: Int, delayMs: Long, cond: () -> Boolean): Boolean {
        for (i in 0 until maxTries) {
            if (cond()) return true
            try {
                Thread.sleep(delayMs)
            } catch (_: InterruptedException) {
                return false
            }
        }
        return false
    }

    private fun notify(project: Project, result: Result) {
        ApplicationManager.getApplication().invokeLater {
            val type = if (result.ok) NotificationType.INFORMATION else NotificationType.WARNING
            val group = NotificationGroupManager.getInstance()
                .getNotificationGroup("PythonAssistant.Notifications")
            val content = if (result.detail.isBlank()) result.title else "${result.title}\n${result.detail}"
            val n = group.createNotification("Python 代码助手", content, type)
            if (!result.ok) {
                n.addAction(
                    NotificationAction.createSimple("打开配置") {
                        ApiConfigDialog(project).show()
                    }
                )
            }
            n.notify(project)
        }
    }

    private data class Result(val ok: Boolean, val title: String, val detail: String)
}
