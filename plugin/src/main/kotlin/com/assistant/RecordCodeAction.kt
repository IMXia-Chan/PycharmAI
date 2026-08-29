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

/** 把当前选中(或整个文件)的代码记录到本地文件库。 */
class RecordCodeAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = FileEditorManager.getInstance(project).selectedTextEditor ?: return
        val doc = editor.document
        val sel = editor.selectionModel
        val hasSelection = sel.hasSelection()
        val code = if (hasSelection) sel.selectedText ?: "" else doc.text
        if (code.isBlank()) {
            Messages.showWarningDialog(project, "没有可记录的代码。", "记录错误代码")
            return
        }
        val line = doc.getLineNumber(if (hasSelection) sel.selectionStart else editor.caretModel.offset) + 1
        val filename = FileDocumentManager.getInstance().getFile(doc)?.name ?: "untitled.py"
        val title = Messages.showInputDialog(project, "给这条记录起个简短标题(可选):", "记录错误代码", null) ?: ""

        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "记录代码…", false) {
            override fun run(indicator: ProgressIndicator) {
                try {
                    LocalLibraryStore.addRecord("record", title, code, "", filename, line, "nonstandard", "warning")
                    ApplicationManager.getApplication().invokeLater {
                        Messages.showInfoMessage(project, "已保存到本地文件库。", "记录错误代码")
                    }
                } catch (ex: Exception) {
                    ApplicationManager.getApplication().invokeLater {
                        Messages.showErrorDialog(project, ex.message ?: "记录失败", "错误")
                    }
                }
            }
        })
    }
}
