package com.assistant

import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages

/** 把当前选中的代码保存到本地「文件库」(kind=snippet),之后可和错误记录一起上传网页。 */
object SnippetSaver {
    fun saveCurrent(project: Project) {
        val editor = FileEditorManager.getInstance(project).selectedTextEditor
        if (editor == null) {
            Messages.showWarningDialog(project, "请先在编辑器里选中要保存的代码。", "保存代码片段")
            return
        }
        val doc = editor.document
        val sel = editor.selectionModel
        val hasSelection = sel.hasSelection()
        val code = if (hasSelection) sel.selectedText ?: "" else doc.text
        if (code.isBlank()) {
            Messages.showWarningDialog(project, "请先在编辑器里选中要保存的代码。", "保存代码片段")
            return
        }
        val title = Messages.showInputDialog(
            project, "给这个片段起个名字(方便以后找):", "保存代码片段", null
        ) ?: return
        val line = doc.getLineNumber(if (hasSelection) sel.selectionStart else editor.caretModel.offset) + 1
        val filename = FileDocumentManager.getInstance().getFile(doc)?.name ?: "untitled.py"

        LocalLibraryStore.addRecord("snippet", title, code, "", filename, line, "snippet", "info")
        Messages.showInfoMessage(project, "已把代码片段「${title.ifBlank { "(无标题)" }}」保存到文件库。", "保存代码片段")
    }
}
