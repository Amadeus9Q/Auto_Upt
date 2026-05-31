/**
 * 错误处理工具
 */

/** 安全提取 Error message，非 Error 类型返回 fallback */
export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
