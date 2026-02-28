/**
 * API route for detecting watermarks
 * Server-side route that calls the Python backend watermark service
 * 
 * 功能: 检测文本中是否存在隐形水印
 * - 接收前端的 POST 请求，包含需要检测的文本
 * - 验证输入文本非 empty
 * - 转发请求到 Python FastAPI 后端 (localhost:8000)
 * - 返回水印检测结果和置信度评分
 * 
 * 请求格式:
 * {
 *   text: string  // 需要检测的文本（必需）
 * }
 * 
 * 响应格式:
 * {
 *   isWatermarked: boolean,       // 是否检测到水印
 *   confidenceScore: number,      // 置信度评分 (0-100)
 *   message: string,              // 检测结果的描述信息
 *   payloads: Array | null        // 检测到的水印有效负载详情
 * }
 * 
 * 错误处理:
 * - 400: 文本为空
 * - 500: 后端服务器错误或连接失败
 */

import { NextRequest, NextResponse } from "next/server";

// 从环境变量读取后端服务地址，默认 localhost:8000
const WATERMARK_API_URL =
  process.env.WATERMARK_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    // 解析请求的 JSON 数据
    const body = await request.json();

    // 验证输入文本不为空
    if (!body.text || !body.text.trim()) {
      return NextResponse.json(
        { error: "Text is required" },
        { status: 400 }
      );
    }

    // 构建后端 API 的完整 URL
    const backendUrl = `${WATERMARK_API_URL}/api/watermark/detect`;
    console.log("Calling backend URL:", backendUrl);
    
    // 调用 Python FastAPI 后端服务进行水印检测
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: body.text,
      }),
    });

    // 检查后端响应是否成功
    if (!response.ok) {
      const error = await response.text();
      console.error("Backend error:", error);
      return NextResponse.json(
        { error: "Failed to detect watermark" },
        { status: response.status }
      );
    }

    // 解析并返回后端响应数据
    const data = await response.json();

    return NextResponse.json({
      isWatermarked: data.is_watermarked,
      confidenceScore: data.confidence_score,
      message: data.message,
      payloads: data.payloads,
    });
  } catch (error) {
    // 处理网络或服务错误
    console.error("Watermark detection error:", error);
    return NextResponse.json(
      { error: "Internal server error", details: String(error) },
      { status: 500 }
    );
  }
}
