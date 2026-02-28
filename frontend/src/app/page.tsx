import { WatermarkTool } from "@/components/watermark-tool";
import { Droplets, ShieldCheck, Zap } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col font-body">
      {/* Navigation Header */}
      <header className="border-b border-white/5 bg-background/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="bg-primary/20 p-2 rounded-lg">
              <Droplets className="w-6 h-6 text-accent" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-foreground font-headline">
              Aqua<span className="text-accent">Mark</span>
            </h1>
          </div>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
            <a href="#" className="hover:text-accent transition-colors">How it works</a>
            <a href="#" className="hover:text-accent transition-colors">Security</a>
            <a href="#" className="hover:text-accent transition-colors">API</a>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-8 md:py-12">
        <div className="max-w-3xl mb-12">
          <h2 className="text-4xl md:text-5xl font-extrabold mb-4 font-headline text-foreground leading-tight">
            Protect your content with <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">
              Invisible Watermarks
            </span>
          </h2>
          <p className="text-lg text-muted-foreground leading-relaxed">
            AquaMark uses AI to subtly embed hidden data into your text. 
            Imperceptible to the eye, but persistent for verification.
          </p>
        </div>

        <WatermarkTool />

        {/* Feature Highlights */}
        <section className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="bg-card/50 p-6 rounded-2xl border border-white/5">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4">
              <ShieldCheck className="w-6 h-6 text-accent" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Secure Metadata</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              Metadata is woven into the character structure of the text itself, making it resilient to simple copy-pastes.
            </p>
          </div>
          <div className="bg-card/50 p-6 rounded-2xl border border-white/5">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4">
              <Droplets className="w-6 h-6 text-accent" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Zero Visual Impact</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              The watermarked text looks exactly like the original. No weird characters or visible markers.
            </p>
          </div>
          <div className="bg-card/50 p-6 rounded-2xl border border-white/5">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4">
              <Zap className="w-6 h-6 text-accent" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Instant Processing</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              Powered by Genkit, our watermarking engine processes thousands of words in milliseconds.
            </p>
          </div>
        </section>
      </main>

      <footer className="py-12 border-t border-white/5 bg-background/50">
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-6">
          <p className="text-sm text-muted-foreground">
            © 2024 AquaMark Technologies. All rights reserved.
          </p>
          <div className="flex gap-8 text-sm text-muted-foreground">
            <a href="#" className="hover:text-accent transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-accent transition-colors">Terms of Service</a>
          </div>
        </div>
      </footer>
    </div>
  );
}