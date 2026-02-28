/**
 * API route for embedding watermarks
 * Server-side route that calls the Python backend watermark service
 * 
 * 功能: 将隐形水印嵌入到传入的文本中
 * - 接收前端的 POST 请求
 * - 验证输入文本非 empty
 * - 转发请求到 Python FastAPI 后端 (localhost:8000)
 * - 返回带有水印的文本
 * 
 * 请求格式:
 * {
 *   text: string,          // 需要添加水印的文本（必需）
 *   issuer_id?: number,    // 发行商 ID（可选，默认 1）
 *   model_id?: number,     // 模型 ID（可选，默认 42）
 *   key_id?: number        // 密钥 ID（可选，默认 1）
 * }
 * 
 * 响应格式:
 * {
 *   watermarkedText: string,  // 添加水印后的文本
 *   success: boolean          // 是否成功
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
    const backendUrl = `${WATERMARK_API_URL}/api/watermark/embed`;
    console.log("Calling backend URL:", backendUrl);
    
    // 调用 Python FastAPI 后端服务进行水印嵌入
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: body.text,
        issuer_id: body.issuer_id || 1,
        model_id: body.model_id || 42,
        key_id: body.key_id || 1,
      }),
    });

    // 检查后端响应是否成功
    if (!response.ok) {
      const error = await response.text();
      console.error("Backend error:", error);
      return NextResponse.json(
        { error: "Failed to embed watermark" },
        { status: response.status }
      );
    }

    // 解析并返回后端响应数据
    const data = await response.json();

    return NextResponse.json({
      watermarkedText: data.watermarked_text,
      success: data.success,
    });
  } catch (error) {
    // 处理网络或服务错误
    console.error("Watermark embed error:", error);
    return NextResponse.json(
      { error: "Internal server error", details: String(error) },
      { status: 500 }
    );
  }
}
