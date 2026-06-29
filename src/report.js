export function formatReport(result) {
  const lines = [];
  lines.push('Source2Launch · 项目/论文发布内容生成器');
  lines.push('');
  lines.push(`目标    ${result.target}`);
  lines.push(`项目    ${result.project.name}`);
  lines.push('资料检查 已生成本地检查报告（仅供 CI / 资料完整度参考）');

  if (result.repository.stars !== null || result.repository.topics.length > 0) {
    const parts = [];
    if (result.repository.stars !== null) parts.push(`${result.repository.stars} stars`);
    if (result.repository.topics.length > 0) parts.push(`topics: ${result.repository.topics.join(', ')}`);
    lines.push(`信号    ${parts.join(' · ')}`);
  }

  lines.push('');
  lines.push('检查明细');
  for (const check of result.checks) {
    lines.push(`  ${check.label.padEnd(20)} ${check.summary}`);
  }

  lines.push('');
  lines.push('优先改进');
  if (result.topFixes.length === 0) {
    lines.push('  未发现明显发布资料短板。');
  } else {
    for (const fix of result.topFixes) {
      lines.push(`  [${fix.severity}] ${fix.message}`);
      lines.push(`         → ${fix.fix}`);
    }
  }

  lines.push('');
  lines.push('提示    本地资料检查仅供 CI；发布文案请用：source2launch promote . --platform all');

  return lines.join('\n');
}
