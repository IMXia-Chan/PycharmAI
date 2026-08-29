package com.assistant

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.editor.Editor

/** 编辑器小工具:取「选中/整文件」代码、替换选区。 */
object EditorOps {

    /** 当前选中的代码;没选中则返回整个文件。 */
    fun currentCode(editor: Editor): String {
        val sel = editor.selectionModel
        return if (sel.hasSelection()) sel.selectedText ?: "" else editor.document.text
    }

    /** 用新代码替换当前选区;没选中则替换整个文件。 */
    fun replace(editor: Editor, newText: String) {
        val doc = editor.document
        val sel = editor.selectionModel
        val start = if (sel.hasSelection()) sel.selectionStart else 0
        val end = if (sel.hasSelection()) sel.selectionEnd else doc.textLength
        WriteCommandAction.runWriteCommandAction(editor.project) {
            doc.replaceString(start, end, newText)
        }
    }
}
