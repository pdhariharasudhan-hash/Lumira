import type { ReactNode } from "react";

type InlinePart = { kind: "text" | "code" | "strong" | "em" | "strike" | "link"; value: string; href?: string };

function inlineParts(source: string): InlinePart[] {
	const pattern = /`([^`]+)`|\*\*([^*]+)\*\*|~~([^~]+)~~|\*([^*]+)\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
	const parts: InlinePart[] = [];
	let cursor = 0;
	for (const match of source.matchAll(pattern)) {
		const index = match.index ?? 0;
		if (index > cursor) parts.push({ kind: "text", value: source.slice(cursor, index) });
		if (match[1] !== undefined) parts.push({ kind: "code", value: match[1] });
		else if (match[2] !== undefined) parts.push({ kind: "strong", value: match[2] });
		else if (match[3] !== undefined) parts.push({ kind: "strike", value: match[3] });
		else if (match[4] !== undefined) parts.push({ kind: "em", value: match[4] });
		else if (match[5] !== undefined && match[6] !== undefined) {
			parts.push({ kind: "link", value: match[5], href: match[6] });
		}
		cursor = index + match[0].length;
	}
	if (cursor < source.length) parts.push({ kind: "text", value: source.slice(cursor) });
	return parts;
}

function renderInline(source: string): ReactNode[] {
	return inlineParts(source).map((part, index) => {
		switch (part.kind) {
			case "code": return <code key={index} className="assistant-inline-code">{part.value}</code>;
			case "strong": return <strong key={index}>{part.value}</strong>;
			case "em": return <em key={index}>{part.value}</em>;
			case "strike": return <del key={index}>{part.value}</del>;
			case "link": return <a key={index} href={part.href} target="_blank" rel="noreferrer noopener">{part.value}</a>;
			default: return <span key={index}>{part.value}</span>;
		}
	});
}

function isBlockStart(line: string): boolean {
	return /^\s*(?:#{1,6}\s|> |[-*_]{3,}\s*$|[-*+]\s+|\d+[.)]\s+|```)/.test(line);
}

export function MarkdownMessage({ content }: { content: string }) {
	const lines = content.replace(/\r\n?/g, "\n").split("\n");
	const blocks: ReactNode[] = [];
	let index = 0;

	while (index < lines.length) {
		const line = lines[index];
		if (!line.trim()) { index += 1; continue; }

		const fence = line.match(/^\s*```([\w+-]*)\s*$/);
		if (fence) {
			const language = fence[1];
			index += 1;
			const code: string[] = [];
			while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
				code.push(lines[index]);
				index += 1;
			}
			if (index < lines.length) index += 1;
			blocks.push(<pre className="assistant-code-output" key={blocks.length}><code className={language ? `language-${language}` : undefined}>{code.join("\n")}</code></pre>);
			continue;
		}

		const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
		if (heading) {
			const level = heading[1].length;
			const children = renderInline(heading[2]);
			const Tag = (`h${level}`) as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
			blocks.push(<Tag key={blocks.length} className="assistant-markdown-heading">{children}</Tag>);
			index += 1;
			continue;
		}

		if (/^\s*([-*_])\1\1+\s*$/.test(line)) {
			blocks.push(<hr key={blocks.length} />);
			index += 1;
			continue;
		}

		if (/^\s*>\s?/.test(line)) {
			const quote: string[] = [];
			while (index < lines.length && /^\s*>/.test(lines[index])) {
				quote.push(lines[index].replace(/^\s*>\s?/, ""));
				index += 1;
			}
			blocks.push(<blockquote key={blocks.length}>{quote.map((part, i) => <p key={i}>{renderInline(part)}</p>)}</blockquote>);
			continue;
		}

		const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
		const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
		if (unordered || ordered) {
			const isOrdered = Boolean(ordered);
			const items: string[] = [];
			while (index < lines.length) {
				const match = isOrdered
					? lines[index].match(/^\s*\d+[.)]\s+(.+)$/)
					: lines[index].match(/^\s*[-*+]\s+(.+)$/);
				if (!match) break;
				items.push(match[1]);
				index += 1;
			}
			const ListTag = isOrdered ? "ol" : "ul";
			blocks.push(<ListTag key={blocks.length}>{items.map((item, i) => <li key={i}>{renderInline(item)}</li>)}</ListTag>);
			continue;
		}

		const paragraph: string[] = [line];
		index += 1;
		while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) {
			paragraph.push(lines[index]);
			index += 1;
		}
		blocks.push(<p key={blocks.length}>{paragraph.map((part, i) => <span key={i}>{i > 0 && <br />}{renderInline(part)}</span>)}</p>);
	}

	return <div className="assistant-markdown">{blocks}</div>;
}

export default MarkdownMessage;
