import React, { useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import { Underline } from '@tiptap/extension-underline';
import { Link } from '@tiptap/extension-link';
import { TextAlign } from '@tiptap/extension-text-align';
import { Highlight } from '@tiptap/extension-highlight';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { Subscript } from '@tiptap/extension-subscript';
import { Superscript } from '@tiptap/extension-superscript';
import { TaskList } from '@tiptap/extension-task-list';
import { TaskItem } from '@tiptap/extension-task-item';
import { CharacterCount } from '@tiptap/extension-character-count';

import { 
  Bold, 
  Italic, 
  List, 
  ListOrdered, 
  Heading1, 
  Heading2, 
  Heading3,
  Quote, 
  Undo, 
  Redo,
  Underline as UnderlineIcon,
  Link as LinkIcon,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  Highlighter,
  Table as TableIcon,
  Code,
  Minus,
  Subscript as SubscriptIcon,
  Superscript as SuperscriptIcon,
  CheckSquare,
  Strikethrough,
  Unlink
} from 'lucide-react';
import { cn } from '../lib/utils';

interface RichTextEditorProps {
  content: string;
  onChange: (content: string) => void;
  placeholder?: string;
}

const MenuBar = ({ editor }: { editor: any }) => {
  if (!editor) {
    return null;
  }

  const setLink = useCallback(() => {
    const previousUrl = editor.getAttributes('link').href;
    const url = window.prompt('URL', previousUrl);

    // cancelled
    if (url === null) {
      return;
    }

    // empty
    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }

    // update link
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  }, [editor]);

  const buttons = [
    {
      group: 'History',
      items: [
        { icon: Undo, onClick: () => editor.chain().focus().undo().run(), isActive: false, disabled: !editor.can().undo(), title: 'Hoàn tác' },
        { icon: Redo, onClick: () => editor.chain().focus().redo().run(), isActive: false, disabled: !editor.can().redo(), title: 'Làm lại' },
      ]
    },
    {
      group: 'Headings',
      items: [
        { icon: Heading1, onClick: () => editor.chain().focus().toggleHeading({ level: 1 }).run(), isActive: editor.isActive('heading', { level: 1 }), title: 'Tiêu đề 1' },
        { icon: Heading2, onClick: () => editor.chain().focus().toggleHeading({ level: 2 }).run(), isActive: editor.isActive('heading', { level: 2 }), title: 'Tiêu đề 2' },
        { icon: Heading3, onClick: () => editor.chain().focus().toggleHeading({ level: 3 }).run(), isActive: editor.isActive('heading', { level: 3 }), title: 'Tiêu đề 3' },
      ]
    },
    {
      group: 'Formatting',
      items: [
        { icon: Bold, onClick: () => editor.chain().focus().toggleBold().run(), isActive: editor.isActive('bold'), title: 'In đậm' },
        { icon: Italic, onClick: () => editor.chain().focus().toggleItalic().run(), isActive: editor.isActive('italic'), title: 'In nghiêng' },
        { icon: UnderlineIcon, onClick: () => editor.chain().focus().toggleUnderline().run(), isActive: editor.isActive('underline'), title: 'Gạch chân' },
        { icon: Strikethrough, onClick: () => editor.chain().focus().toggleStrike().run(), isActive: editor.isActive('strike'), title: 'Gạch ngang' },
        { icon: Highlighter, onClick: () => editor.chain().focus().toggleHighlight().run(), isActive: editor.isActive('highlight'), title: 'Làm nổi bật' },
      ]
    },
    {
      group: 'Alignment',
      items: [
        { icon: AlignLeft, onClick: () => editor.chain().focus().setTextAlign('left').run(), isActive: editor.isActive({ textAlign: 'left' }), title: 'Căn trái' },
        { icon: AlignCenter, onClick: () => editor.chain().focus().setTextAlign('center').run(), isActive: editor.isActive({ textAlign: 'center' }), title: 'Căn giữa' },
        { icon: AlignRight, onClick: () => editor.chain().focus().setTextAlign('right').run(), isActive: editor.isActive({ textAlign: 'right' }), title: 'Căn phải' },
        { icon: AlignJustify, onClick: () => editor.chain().focus().setTextAlign('justify').run(), isActive: editor.isActive({ textAlign: 'justify' }), title: 'Căn đều' },
      ]
    },
    {
      group: 'Lists',
      items: [
        { icon: List, onClick: () => editor.chain().focus().toggleBulletList().run(), isActive: editor.isActive('bulletList'), title: 'Danh sách' },
        { icon: ListOrdered, onClick: () => editor.chain().focus().toggleOrderedList().run(), isActive: editor.isActive('orderedList'), title: 'Danh sách số' },
        { icon: CheckSquare, onClick: () => editor.chain().focus().toggleTaskList().run(), isActive: editor.isActive('taskList'), title: 'Danh sách công việc' },
      ]
    },
    {
      group: 'Insert',
      items: [
        { icon: LinkIcon, onClick: setLink, isActive: editor.isActive('link'), title: 'Chèn link' },
        { icon: Unlink, onClick: () => editor.chain().focus().unsetLink().run(), isActive: false, disabled: !editor.isActive('link'), title: 'Bỏ link' },
        { icon: Quote, onClick: () => editor.chain().focus().toggleBlockquote().run(), isActive: editor.isActive('blockquote'), title: 'Trích dẫn' },
        { icon: Code, onClick: () => editor.chain().focus().toggleCodeBlock().run(), isActive: editor.isActive('codeBlock'), title: 'Khối mã' },
        { icon: Minus, onClick: () => editor.chain().focus().setHorizontalRule().run(), isActive: false, title: 'Đường kẻ ngang' },
      ]
    },
    {
      group: 'Table',
      items: [
        { icon: TableIcon, onClick: () => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(), isActive: editor.isActive('table'), title: 'Chèn bảng' },
      ]
    },
    {
      group: 'Script',
      items: [
        { icon: SubscriptIcon, onClick: () => editor.chain().focus().toggleSubscript().run(), isActive: editor.isActive('subscript'), title: 'Chỉ số dưới' },
        { icon: SuperscriptIcon, onClick: () => editor.chain().focus().toggleSuperscript().run(), isActive: editor.isActive('superscript'), title: 'Chỉ số trên' },
      ]
    }
  ];

  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2 p-2 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 rounded-t-xl sticky top-0 z-10">
      {buttons.map((group, groupIdx) => (
        <div key={groupIdx} className="flex items-center gap-1 pr-4 border-r border-slate-200 dark:border-slate-700 last:border-r-0">
          {group.items.map((btn, i) => (
            <button
              key={i}
              onClick={(e) => {
                e.preventDefault();
                btn.onClick();
              }}
              disabled={btn.disabled}
              title={btn.title}
              className={cn(
                "p-1.5 rounded-md transition-all",
                btn.isActive 
                  ? "bg-white dark:bg-slate-800 text-accent shadow-sm ring-1 ring-slate-200 dark:ring-slate-600"
                  : "text-slate-500 dark:text-slate-400 hover:bg-white dark:hover:bg-slate-700 hover:text-slate-900 dark:hover:text-white hover:shadow-sm",
                btn.disabled && "opacity-30 cursor-not-allowed"
              )}
            >
              <btn.icon size={16} />
            </button>
          ))}
        </div>
      ))}
    </div>
  );
};

export default function RichTextEditor({ content, onChange, placeholder }: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Placeholder.configure({
        placeholder: placeholder || 'Bắt đầu soạn thảo...',
      }),
      Underline,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-accent underline cursor-pointer',
        },
      }),
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      Highlight.configure({ multicolor: true }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
      Subscript,
      Superscript,
      TaskList,
      TaskItem.configure({
        nested: true,
      }),
      CharacterCount,
    ],
    content,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none focus:outline-none min-h-[200px] p-4 text-slate-700 dark:text-slate-200',
      },
    },
  });

  return (
    <div className="w-full border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 overflow-hidden focus-within:ring-2 focus-within:ring-accent/20 focus-within:border-accent transition-all">
      <MenuBar editor={editor} />
      <EditorContent editor={editor} />
      <div className="px-4 py-2 bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-700 flex justify-between items-center text-[10px] text-slate-400 dark:text-slate-500 font-medium">
        <div className="flex gap-4">
          <span>{editor?.storage.characterCount?.characters() || 0} ký tự</span>
          <span>{editor?.storage.characterCount?.words() || 0} từ</span>
        </div>
        <div className="flex gap-2">
          {editor?.isActive('table') && (
            <div className="flex gap-1">
              <button onClick={() => editor.chain().focus().addColumnBefore().run()} className="hover:text-accent">Thêm cột</button>
              <button onClick={() => editor.chain().focus().addRowBefore().run()} className="hover:text-accent">Thêm hàng</button>
              <button onClick={() => editor.chain().focus().deleteTable().run()} className="hover:text-danger">Xóa bảng</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
