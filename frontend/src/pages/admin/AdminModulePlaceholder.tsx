type AdminModulePlaceholderProps = {
  description: string
}

/**
 * 仅为尚未进入业务开发的管理员菜单提供独立页面容器。
 * 页面标题统一由全局 Header 根据路由显示，避免内容区重复渲染标题。
 */
export function AdminModulePlaceholder({ description }: AdminModulePlaceholderProps) {
  return (
    <section className="admin-module-placeholder">
      <p>{description}</p>
      <div className="admin-module-placeholder__status">功能建设中</div>
    </section>
  )
}
