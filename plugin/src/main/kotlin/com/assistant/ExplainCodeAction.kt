package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.ui.Messages

/** 选中一段代码 → 用中文解释它在干嘛。 */
class ExplainCodeAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = FileEditorManager.getInstance(project).selectedTextEditor ?: return
        val code = EditorOps.currentCode(editor)
        if (code.isBlank()) {
            Messages.showWarningDialog(project, "请先选中一段代码。", "解释代码")
            return
        }
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "AI 正在解释…", false) {
            override fun run(indicator: ProgressIndicator) {
                val text = try {
                    BackendClient.explain(code)
                } catch (ex: Exception) {
                    "请求失败:${ex.message ?: "请确认后端已启动"}"
                }
                // 存入本地文件库:把这次「代码解释」也存成一条记录
                try {
                    val filename = FileDocumentManager.getInstance().getFile(editor.document)?.name ?: "untitled.py"
                    val line = editor.document.getLineNumber(editor.caretModel.offset) + 1
                    LocalLibraryStore.addRecord("explain", "代码解释", code, text, filename, line, "explain", "info")
                } catch (_: Exception) {
                    // 记录失败不影响主功能
                }
                ApplicationManager.getApplication().invokeLater {
                    AiResultDialog(project, "解释代码", text).show()
                }
            }
        })
    }
}
