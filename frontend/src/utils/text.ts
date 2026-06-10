/**
 * 文本工具函数
 */

/** 将逗号/空格/全角逗号分隔的标签文本解析为字符串数组 */
export function parseTagText(value: string): string[] {
  return value
    .split(/[,，\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}
