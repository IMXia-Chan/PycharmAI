package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.ui.components.JBScrollPane
import javax.swing.JComponent
import javax.swing.JTextArea

/** 粘贴一段运行时报错 → AI 解释为什么错、怎么改。 */
class ExplainErrorAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val dialog = ErrorInputDialog(project)
        if (!dialog.showAndGet()) return
        val error = dialog.text()
        if (error.isBlank()) return

        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "AI 正在分析报错…", false) {
            override fun run(indicator: ProgressIndicator) {
                val text = try {
                    BackendClient.explainError(error)
                } catch (ex: Exception) {
                    "请求失败:${ex.message ?: "请确认后端已启动"}"
                }
                // 存入本地文件库:把这次「报错解释」也存成一条记录
                try {
                    LocalLibraryStore.addRecord("error-explain", "报错解释", error, text, "报错解释", 0, "error-explain", "info")
                } catch (_: Exception) {
                    // 记录失败不影响主功能
                }
                ApplicationManager.getApplication().invokeLater {
                    AiResultDialog(project, "报错解释", text).show()
                }
            }
        })
    }
}

/** 多行输入弹窗,用于粘贴报错信息。 */
private class ErrorInputDialog(project: Project) : DialogWrapper(project) {
    private val area = JTextArea().apply {
        lineWrap = true
        wrapStyleWord = true
        rows = 12
        columns = 60
    }

    init {
        title = "报错解释"
        init()
    }

    override fun createCenterPanel(): JComponent = JBScrollPane(area)

    fun text(): String = area.text.trim()
}
