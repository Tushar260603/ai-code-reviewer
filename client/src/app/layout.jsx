import "./globals.css";

export const metadata = {
  title: "AI Code Reviewer - Automated PR Analytics & Review",
  description: "Automated multi-agent code reviews for GitHub pull requests.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
