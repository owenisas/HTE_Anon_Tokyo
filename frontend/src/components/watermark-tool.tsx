"use client";

import React, { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { Copy, Check, Droplets, RotateCcw, Sparkles, FileText, Search, ShieldCheck as ShieldCheckIcon, AlertCircle } from "lucide-react";
import { embedHiddenTextWatermark } from "@/ai/flows/embed-hidden-text-watermark";
import { detectWatermark } from "@/ai/flows/detect-watermark-flow";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

const DEMO_TEXTS = [
  "In the world of professional content creation, the risk of unauthorized distribution is constant. Using AquaMark allows creators to maintain an invisible trace of ownership within their documents without distracting the reader or compromising the aesthetic of the typography.",
  "Sensitive internal communications require an additional layer of security. By watermarking internal reports, organizations can trace the source of potential leaks back to the specific version shared with an individual, even if the text is copied manually into a new document.",
  "Project Stealth is moving into its final phase. The hardware prototypes are ready for stress testing in the subterranean labs. All team members must report to their stations by 08:00 UTC for the synchronization event."
];

export function WatermarkTool() {
  const [inputText, setInputText] = useState("");
  const [outputItems, setOutputItems] = useState<{ id: number; text: string; date: Date } | null>(null);
  const [detectionResult, setDetectionResult] = useState<{ score: number; isWatermarked: boolean; message: string } | null>(null);
  const [isCopied, setIsCopied] = useState(false);
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  const handleWatermark = async () => {
    if (!inputText.trim()) {
      toast({
        title: "Input required",
        description: "Please enter some text to watermark.",
        variant: "destructive",
      });
      return;
    }

    startTransition(async () => {
      try {
        const result = await embedHiddenTextWatermark({ originalText: inputText });
        setOutputItems({
          id: Date.now(),
          text: result.watermarkedText,
          date: new Date(),
        });
        toast({
          title: "Success",
          description: "Invisible watermark embedded successfully.",
        });
      } catch (error: any) {
        toast({
          title: "Watermarking Failed",
          description: error?.message || "An unexpected error occurred while embedding the watermark.",
          variant: "destructive",
        });
      }
    });
  };

  const handleDetect = async () => {
    if (!inputText.trim()) {
      toast({
        title: "Input required",
        description: "Please enter some text to analyze.",
        variant: "destructive",
      });
      return;
    }

    startTransition(async () => {
      try {
        const result = await detectWatermark({ text: inputText });
        setDetectionResult({
          score: result.confidenceScore,
          isWatermarked: result.isWatermarked,
          message: result.message,
        });
        toast({
          title: "Analysis Complete",
          description: `Detection score: ${result.confidenceScore}%`,
        });
      } catch (error: any) {
        toast({
          title: "Detection Failed",
          description: error?.message || "An error occurred during verification.",
          variant: "destructive",
        });
      }
    });
  };

  const handleCopy = () => {
    if (!outputItems) return;
    navigator.clipboard.writeText(outputItems.text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
    toast({
      title: "Copied",
      description: "Watermarked text copied to clipboard.",
    });
  };

  const loadDemo = () => {
    const randomDemo = DEMO_TEXTS[Math.floor(Math.random() * DEMO_TEXTS.length)];
    setInputText(randomDemo);
    toast({
      title: "Demo Loaded",
      description: "Sample text has been added to the input field.",
    });
  };

  const reset = () => {
    setInputText("");
    setOutputItems(null);
    setDetectionResult(null);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
      {/* Left Column: Input and Actions */}
      <Card className={cn(
        "bg-card/30 border-white/5 relative overflow-hidden group transition-all duration-500",
        isPending && "watermark-glow"
      )}>
        {/* Loading Overlay */}
        {isPending && (
          <div className="absolute inset-0 z-10 bg-background/40 backdrop-blur-[2px] rounded-lg flex flex-col items-center justify-center pointer-events-none overflow-hidden">
            <div className="absolute inset-x-0 h-24 bg-gradient-to-b from-transparent via-accent/20 to-transparent animate-scan"></div>
            <Sparkles className="w-12 h-12 text-accent animate-pulse mb-4" />
            <p className="text-accent font-medium tracking-widest text-sm uppercase">Processing AI Analytics</p>
          </div>
        )}

        <CardHeader className="flex flex-row items-center justify-between pb-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-primary font-headline">
              <FileText className="w-5 h-5 text-accent" />
              Content Workspace
            </CardTitle>
            <CardDescription>Input text for protection or verification</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={loadDemo} 
              className="text-xs h-8 border-white/10 hover:bg-white/5"
            >
              Load Demo
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={reset} 
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Textarea
              placeholder="Paste your content here to watermark it, or paste suspected content to verify..."
              className="min-h-[350px] bg-background/50 border-white/10 focus-visible:ring-accent resize-none p-6 text-base leading-relaxed"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Button
              onClick={handleWatermark}
              disabled={isPending || !inputText.trim()}
              className="bg-primary hover:bg-primary/80 text-primary-foreground font-semibold h-12 gap-2 text-base transition-all active:scale-[0.98]"
            >
              <Droplets className="w-5 h-5" />
              Protect
            </Button>
            <Button
              variant="secondary"
              onClick={handleDetect}
              disabled={isPending || !inputText.trim()}
              className="font-semibold h-12 gap-2 text-base transition-all active:scale-[0.98] border border-white/5"
            >
              <Search className="w-5 h-5" />
              Verify AI Rate
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Right Column: Output / Detection Results */}
      <div className="space-y-6">
        <Tabs defaultValue="results" className="w-full">
          <TabsList className="grid w-full grid-cols-2 bg-card/50 border border-white/5">
            <TabsTrigger value="results">Security Output</TabsTrigger>
            <TabsTrigger value="verification">Verification Analytics</TabsTrigger>
          </TabsList>
          
          <TabsContent value="results">
            <Card className="bg-card/30 border-white/5 relative min-h-[500px] flex flex-col transition-all duration-500">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-primary font-headline">
                      <ShieldCheckIcon className="w-5 h-5 text-accent" />
                      Watermarked Result
                    </CardTitle>
                    <CardDescription>Stealth trace successfully woven</CardDescription>
                  </div>
                  {outputItems && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCopy}
                      className={cn(
                        "h-8 gap-2 transition-all",
                        isCopied ? "bg-accent/20 border-accent/50 text-accent" : "border-white/10"
                      )}
                    >
                      {isCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      {isCopied ? "Copied" : "Copy Result"}
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col">
                {!outputItems ? (
                  <div className="flex-1 border-2 border-dashed border-white/5 rounded-lg flex flex-col items-center justify-center p-12 text-center opacity-40">
                    <Droplets className="w-12 h-12 text-primary mb-4" />
                    <p className="max-w-[240px] text-sm text-muted-foreground italic leading-relaxed">
                      Watermarked text will be generated here.
                    </p>
                  </div>
                ) : (
                  <div className="flex-1 bg-background/20 rounded-lg p-6 font-normal text-base leading-relaxed text-foreground select-all border border-white/5 whitespace-pre-wrap">
                    {outputItems.text}
                    <div className="mt-8 pt-4 border-t border-white/5 flex justify-between items-center text-[10px] text-muted-foreground font-code uppercase tracking-widest">
                      <span>Verification: PERSISTENT</span>
                      <span>TRACE_ID: {outputItems.id}</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="verification">
            <Card className="bg-card/30 border-white/5 relative min-h-[500px] flex flex-col transition-all duration-500">
              <CardHeader className="pb-4">
                <CardTitle className="flex items-center gap-2 text-primary font-headline">
                  <Search className="w-5 h-5 text-accent" />
                  Forensic Analytics
                </CardTitle>
                <CardDescription>AI patterns and watermark verification</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col">
                {!detectionResult ? (
                  <div className="flex-1 border-2 border-dashed border-white/5 rounded-lg flex flex-col items-center justify-center p-12 text-center opacity-40">
                    <AlertCircle className="w-12 h-12 text-accent mb-4" />
                    <p className="max-w-[240px] text-sm text-muted-foreground italic leading-relaxed">
                      Run "Verify AI Rate" to see forensic analysis of the input text.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
                    <div className="bg-background/40 p-6 rounded-xl border border-white/5">
                      <div className="flex justify-between items-end mb-4">
                        <span className="text-sm font-medium text-muted-foreground uppercase tracking-widest">Watermark AI Rate</span>
                        <span className={cn(
                          "text-3xl font-bold font-headline",
                          detectionResult.score > 70 ? "text-accent" : "text-muted-foreground"
                        )}>
                          {detectionResult.score}%
                        </span>
                      </div>
                      <Progress value={detectionResult.score} className="h-3 bg-white/5" />
                      <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
                        {detectionResult.message}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-card/50 p-4 rounded-lg border border-white/5">
                        <span className="block text-[10px] text-muted-foreground uppercase mb-1">Status</span>
                        <span className={cn(
                          "font-semibold",
                          detectionResult.isWatermarked ? "text-accent" : "text-destructive"
                        )}>
                          {detectionResult.isWatermarked ? "VERIFIED" : "CLEAN / UNKNOWN"}
                        </span>
                      </div>
                      <div className="bg-card/50 p-4 rounded-lg border border-white/5">
                        <span className="block text-[10px] text-muted-foreground uppercase mb-1">Certainty</span>
                        <span className="font-semibold text-foreground">
                          {detectionResult.score > 90 ? "CRITICAL" : detectionResult.score > 50 ? "MODERATE" : "LOW"}
                        </span>
                      </div>
                    </div>

                    <div className="p-4 bg-primary/5 rounded-lg border border-primary/10">
                      <h4 className="text-xs font-semibold text-primary uppercase mb-2">Technical Summary</h4>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        The AI engine scanned the character encoding layer for non-visible Unicode patterns (U+200B). 
                        {detectionResult.isWatermarked 
                          ? " The frequency and distribution matches the AquaMark stealth protocol."
                          : " No significant hidden markers were identified in this text sample."}
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}