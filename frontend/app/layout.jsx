import "./globals.css";
export const metadata = {
  title: "FinRAG · Meridian Research Workspace",
  description: "Evidence-oriented financial research over original reports.",
};
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
