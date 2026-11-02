import type { AnchorHTMLAttributes } from "react";
import { Link } from "react-router-dom";

/** Links para telas já migradas (/app/...) navegam dentro do app, sem recarregar; os demais abrem a página atual. */
export function SmartLink({ href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  if (href === "/app" || href.startsWith("/app/")) {
    return <Link to={href.slice(4) || "/"} {...props} />;
  }
  return <a href={href} {...props} />;
}
