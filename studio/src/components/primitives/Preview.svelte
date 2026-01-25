<!--
  Preview Primitive (RFC-072, RFC-078)
  
  Live preview for web content, markdown, code, images, and PDFs.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {
    url?: string;
    content?: string;
    contentType?: 'markdown' | 'code' | 'image' | 'pdf' | 'text' | 'html';
    language?: string;
    filePath?: string;
  }
  
  let { 
    size, 
    url, 
    content, 
    contentType = 'text',
    language = 'text',
    filePath,
  }: Props = $props();
  
  // Infer content type from file path or URL if not specified
  const inferredContentType = $derived.by(() => {
    if (contentType !== 'text') return contentType;
    
    const path = filePath || url || '';
    const ext = path.split('.').pop()?.toLowerCase() || '';
    
    const markdownExts = ['md', 'markdown', 'mdown', 'mkd'];
    const codeExts = [
      'py', 'js', 'ts', 'jsx', 'tsx', 'rs', 'go', 'java', 'c', 'cpp',
      'h', 'hpp', 'cs', 'rb', 'php', 'swift', 'kt', 'scala', 'sh',
      'bash', 'zsh', 'yaml', 'yml', 'json', 'toml', 'xml', 'css',
      'scss', 'sass', 'less', 'sql', 'graphql'
    ];
    const imageExts = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp'];
    const htmlExts = ['html', 'htm'];
    
    if (markdownExts.includes(ext)) return 'markdown';
    if (codeExts.includes(ext)) return 'code';
    if (imageExts.includes(ext)) return 'image';
    if (ext === 'pdf') return 'pdf';
    if (htmlExts.includes(ext)) return 'html';
    
    return 'text';
  });
  
  // Get language from file extension for code highlighting
  const inferredLanguage = $derived.by(() => {
    if (language !== 'text') return language;
    
    const path = filePath || url || '';
    const ext = path.split('.').pop()?.toLowerCase() || '';
    
    const langMap: Record<string, string> = {
      'py': 'python',
      'js': 'javascript',
      'ts': 'typescript',
      'jsx': 'javascript',
      'tsx': 'typescript',
      'rs': 'rust',
      'go': 'go',
      'java': 'java',
      'c': 'c',
      'cpp': 'cpp',
      'h': 'c',
      'hpp': 'cpp',
      'cs': 'csharp',
      'rb': 'ruby',
      'php': 'php',
      'swift': 'swift',
      'kt': 'kotlin',
      'yaml': 'yaml',
      'yml': 'yaml',
      'json': 'json',
      'toml': 'toml',
      'xml': 'xml',
      'html': 'html',
      'css': 'css',
      'scss': 'scss',
      'sql': 'sql',
      'sh': 'bash',
      'bash': 'bash',
    };
    
    return langMap[ext] || ext;
  });
  
  // Simple markdown to HTML conversion (basic implementation)
  function renderMarkdown(md: string): string {
    let html = md
      // Code blocks
      .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Headers
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      // Bold
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
      // Images
      .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" />')
      // Blockquotes
      .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
      // Horizontal rules
      .replace(/^---$/gm, '<hr />')
      // Unordered lists
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      // Paragraphs (simple - just wrap non-tagged lines)
      .replace(/^(?!<[a-z]|$)(.+)$/gm, '<p>$1</p>');
    
    // Wrap list items in <ul>
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    
    return html;
  }
  
  // Escape HTML for code display
  function escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
  
  // Add line numbers to code
  function addLineNumbers(code: string): string {
    const lines = code.split('\n');
    return lines.map((line, i) => {
      const lineNum = String(i + 1).padStart(3, ' ');
      return `<span class="line-number">${lineNum}</span>${escapeHtml(line)}`;
    }).join('\n');
  }
  
  // Get display name from path
  const displayName = $derived.by(() => {
    if (filePath) {
      return filePath.split('/').pop() || filePath;
    }
    if (url) {
      try {
        return new URL(url).pathname.split('/').pop() || url;
      } catch {
        return url;
      }
    }
    return 'Preview';
  });
</script>

<div class="preview" data-size={size}>
  <div class="preview-header">
    <span>👁️ Preview</span>
    <div class="preview-info">
      {#if filePath || url}
        <span class="preview-path" title={filePath || url}>{displayName}</span>
      {/if}
      <span class="content-type">{inferredContentType}</span>
    </div>
  </div>
  <div class="preview-content">
    {#if url && inferredContentType === 'html'}
      <!-- HTML iframe preview -->
      <iframe 
        src={url} 
        title="Preview"
        sandbox="allow-scripts allow-same-origin"
      ></iframe>
    {:else if inferredContentType === 'image'}
      <!-- Image preview -->
      <div class="image-container">
        <img 
          src={url || `data:image/*;base64,${content}`} 
          alt={displayName} 
          loading="lazy"
        />
      </div>
    {:else if inferredContentType === 'pdf'}
      <!-- PDF preview -->
      {#if url}
        <iframe 
          src={url} 
          title="PDF Preview"
          class="pdf-viewer"
        ></iframe>
      {:else}
        <p class="placeholder">PDF preview requires a URL</p>
      {/if}
    {:else if inferredContentType === 'markdown' && content}
      <!-- Markdown preview -->
      <div class="markdown-content">
        {@html renderMarkdown(content)}
      </div>
    {:else if inferredContentType === 'code' && content}
      <!-- Code preview with syntax highlighting -->
      <div class="code-content" data-language={inferredLanguage}>
        <div class="code-header">
          <span class="language-badge">{inferredLanguage}</span>
        </div>
        <pre><code>{@html addLineNumbers(content)}</code></pre>
      </div>
    {:else if content}
      <!-- Plain text preview -->
      <div class="text-content">
        <pre>{content}</pre>
      </div>
    {:else if url}
      <!-- Fallback iframe for unknown URL types -->
      <iframe src={url} title="Preview"></iframe>
    {:else}
      <p class="placeholder">No preview available</p>
    {/if}
  </div>
</div>

<style>
  .preview {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .preview-info {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }
  
  .preview-path {
    font-size: 0.75rem;
    color: var(--text-secondary);
    font-family: var(--font-mono);
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .content-type {
    font-size: 0.625rem;
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    text-transform: uppercase;
  }
  
  .preview-content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }
  
  .preview-content iframe {
    width: 100%;
    height: 100%;
    border: none;
    background: white;
  }
  
  .pdf-viewer {
    background: var(--bg-tertiary);
  }
  
  .image-container {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-md);
    overflow: auto;
    background: var(--bg-tertiary);
  }
  
  .image-container img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: var(--radius-sm);
  }
  
  .markdown-content {
    width: 100%;
    height: 100%;
    overflow: auto;
    padding: var(--spacing-md) var(--spacing-lg);
    color: var(--text-primary);
    line-height: 1.6;
  }
  
  .markdown-content :global(h1) {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 1.5rem 0 0.75rem;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 0.5rem;
  }
  
  .markdown-content :global(h2) {
    font-size: 1.375rem;
    font-weight: 600;
    margin: 1.25rem 0 0.5rem;
  }
  
  .markdown-content :global(h3) {
    font-size: 1.125rem;
    font-weight: 600;
    margin: 1rem 0 0.5rem;
  }
  
  .markdown-content :global(p) {
    margin: 0.75rem 0;
  }
  
  .markdown-content :global(code) {
    font-family: var(--font-mono);
    font-size: 0.875em;
    background: var(--bg-tertiary);
    padding: 0.125rem 0.375rem;
    border-radius: var(--radius-sm);
  }
  
  .markdown-content :global(pre) {
    background: var(--bg-tertiary);
    padding: var(--spacing-md);
    border-radius: var(--radius-md);
    overflow-x: auto;
    margin: 0.75rem 0;
  }
  
  .markdown-content :global(pre code) {
    background: none;
    padding: 0;
  }
  
  .markdown-content :global(blockquote) {
    border-left: 3px solid var(--accent-primary);
    margin: 0.75rem 0;
    padding-left: var(--spacing-md);
    color: var(--text-secondary);
  }
  
  .markdown-content :global(ul) {
    margin: 0.5rem 0;
    padding-left: 1.5rem;
  }
  
  .markdown-content :global(li) {
    margin: 0.25rem 0;
  }
  
  .markdown-content :global(a) {
    color: var(--accent-primary);
    text-decoration: none;
  }
  
  .markdown-content :global(a:hover) {
    text-decoration: underline;
  }
  
  .markdown-content :global(hr) {
    border: none;
    border-top: 1px solid var(--border-subtle);
    margin: 1rem 0;
  }
  
  .markdown-content :global(img) {
    max-width: 100%;
    border-radius: var(--radius-md);
  }
  
  .code-content {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .code-header {
    padding: var(--spacing-xs) var(--spacing-md);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .language-badge {
    font-size: 0.625rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-weight: 600;
  }
  
  .code-content pre {
    flex: 1;
    margin: 0;
    padding: var(--spacing-md);
    overflow: auto;
    background: var(--bg-tertiary);
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    line-height: 1.5;
  }
  
  .code-content code {
    display: block;
    white-space: pre;
  }
  
  .code-content :global(.line-number) {
    display: inline-block;
    width: 3ch;
    margin-right: 1rem;
    color: var(--text-tertiary);
    text-align: right;
    user-select: none;
  }
  
  .text-content {
    width: 100%;
    height: 100%;
    overflow: auto;
    padding: var(--spacing-md);
  }
  
  .text-content pre {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.875rem;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }
  
  .placeholder {
    color: var(--text-tertiary);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
  }
</style>
