package com.assistant

import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project

/** 一键重载知识库索引:灌库后点一下,后端立刻读到新数据,无需重启后端 / PyCharm。 */
class KbReloadAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "重载知识库索引…", false) {
            override fun run(indicator: ProgressIndicator) {
                val (pub, priv) = try {
                    BackendClient.reloadKb()
                } catch (ex: Exception) {
                    notify(project, "重载失败:${ex.message ?: "请确认后端已启动"}", NotificationType.ERROR)
                    return
                }
                notify(project, "知识库索引已重载:公共库 $pub 条,个人库 $priv 条", NotificationType.INFORMATION)
            }
        })
    }

    private fun notify(project: Project, content: String, type: NotificationType) {
        ApplicationManager.getApplication().invokeLater {
            NotificationGroupManager.getInstance()
                .getNotificationGroup("PythonAssistant.Notifications")
                .createNotification("Python 代码助手", content, type)
                .notify(project)
        }
    }
}
