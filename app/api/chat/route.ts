import { Message, StreamingTextResponse } from "ai";
import { OpenAI } from "llamaindex";
import { LlamaDeuce } from "llamaindex";
import { Anthropic } from "llamaindex";
// import { Groq } from "@llamaindex/groq";
import { Gemini, GEMINI_MODEL } from "@llamaindex/google";
import { NextRequest, NextResponse } from "next/server";
import { createChatEngine } from "./engine";
import { LlamaIndexStream } from "./llamaindex-stream";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { messages }: { messages: Message[] } = body;
    const lastMessage = messages.pop();
    if (!messages || !lastMessage || lastMessage.role !== "user") {
      return NextResponse.json(
        {
          error:
            "messages are required in the request body and the last message must be from the user",
        },
        { status: 400 },
      );
    }

    const llm = new OpenAI({
      model: "gpt-4",
    });
    // const llm = new OpenAI({
    //   model: "gpt-3.5-turbo",
    // });
    // const llm = new Groq({
    //   model: "llama3-70b-8192",
    // });

    // const llm = new Gemini({
    //   model: GEMINI_MODEL.GEMINI_PRO,
    // });
    // const llm = new LlamaDeuce({
    //   model: "Llama-2-13b-chat-4bit",
    // });
    // const llm = new Anthropic({
    //   model: "claude-2",
    // });

    const chatEngine = await createChatEngine(llm);

    const response = await chatEngine.chat(lastMessage.content, messages, true);

    // Transform the response into a readable stream
    const stream = LlamaIndexStream(response);

    // Return a StreamingTextResponse, which can be consumed by the client
    return new StreamingTextResponse(stream);
  } catch (error) {
    console.error("[LlamaIndex]", error);
    return NextResponse.json(
      {
        error: (error as Error).message,
      },
      {
        status: 500,
      },
    );
  }
}
