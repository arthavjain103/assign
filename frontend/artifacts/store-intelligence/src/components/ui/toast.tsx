import * as React from "react"

export interface ToastProps {
  id?: string
  open?: boolean
  onOpenChange?: (open: boolean) => void
  title?: React.ReactNode
  description?: React.ReactNode
  action?: ToastActionElement
  variant?: "default" | "destructive"
}

export interface ToastActionElement {
  altText: string
  action: React.ReactNode
}

export const Toast: React.FC<ToastProps> = ({
  open = true,
  title,
  description,
  action,
  onOpenChange,
  variant = "default",
}) => {
  if (!open) return null

  return (
    <div
      className={`fixed bottom-4 right-4 p-4 rounded-md shadow-lg ${
        variant === "destructive"
          ? "bg-red-600 text-white"
          : "bg-slate-900 text-white"
      }`}
    >
      {title && <div className="font-semibold">{title}</div>}
      {description && <div className="text-sm">{description}</div>}
      {action && (
        <div className="mt-2 flex justify-between items-center">
          {action.action}
        </div>
      )}
    </div>
  )
}
