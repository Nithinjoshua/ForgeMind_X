import type { Metadata } from "next";
import "./styles.css";
export const metadata: Metadata = { title: "ForgeMind X | Local Engineering Demo", description: "Rules-based engineering workflow demo" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
