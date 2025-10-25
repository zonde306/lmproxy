import typing
import logging
import middleware
import context

logger = logging.getLogger(__name__)

class TextContentPart(typing.TypedDict):
    type: typing.Literal["text"]
    text: str

class ImageURL(typing.TypedDict):
    url: str
    detail: typing.Literal["auto", "low", "high"]

class ImageContentPart(typing.TypedDict):
    type: typing.Literal["image_url"]
    image_url: ImageURL

ContentPart = TextContentPart | ImageContentPart

class Text(typing.TypedDict):
    role: str
    content: str | list[ContentPart]

class Insertion(typing.TypedDict):
    order: int
    role: str
    content: str | list[ContentPart]
    before: bool
    keywords: list[str] | str

class InjectMiddleware(middleware.Middleware):
    async def process_request(self, ctx: context.Context) -> None:
        if ctx.type == "text":
            self.insert(ctx.body["messages"], self.settings.get("insertions", []))
    
    def insert(self, messages: list[Text], insertions: list[Insertion]) -> None:
        """
        Inserts a list of 'insertions' into a list of 'messages'.

        The 'before' flag in an insertion determines if the new content is prepended
        (for merges) or inserted before the target index (for new messages).
        """
        contents = [ x["content"] for x in messages if isinstance(x.get("content", None), str) ]
        insertions = [ x for x in insertions if self.matchKeywords(x.get("keywords", []), contents) ]

        if not insertions:
            return

        # Sort insertions by order in descending order for stable indexing.
        sorted_insertions = sorted(insertions, key=lambda x: x["order"], reverse=True)

        for insertion in sorted_insertions:
            order = insertion.get("order", 4)
            role_to_insert = insertion.get("role", "any")
            content_to_insert = insertion.get("content", insertion if isinstance(insertion, str) else "")
            # Default to False if 'before' is not specified.
            before = insertion.get("before", False)
            if not content_to_insert:
                continue

            try:
                target_message = messages[order]

                if role_to_insert == "any" or target_message["role"] == role_to_insert:
                    # MERGE operation
                    merged_content = self._merge_content(
                        target_message["content"], 
                        content_to_insert,
                        before=before
                    )
                    target_message["content"] = merged_content
                else:
                    # INSERT operation (roles differ)
                    new_message: Text = {"role": role_to_insert, "content": content_to_insert}
                    if before:
                        # Insert at the specified index.
                        messages.insert(order, new_message)
                    else:
                        # Insert *after* the specified index.
                        # Handle the edge case where order is -1 (last element).
                        # order + 1 would become 0, which is incorrect.
                        if order == -1:
                            messages.append(new_message)
                        else:
                            messages.insert(order + 1, new_message)

            except IndexError:
                # INSERT operation (index was out of bounds)
                # list.insert handles this gracefully. The 'before' flag is
                # less meaningful here as there's no element to be 'before' or 'after'.
                new_message: Text = {"role": role_to_insert, "content": content_to_insert}
                messages.insert(order, new_message)
        
        if self.settings.get("debug", False):
            logger.info(f"Inserted messages: {messages}")
    
    def _to_content_list(self, content: str | list[ContentPart]) -> list[ContentPart]:
        """Helper function to normalize content to a list of ContentParts."""
        if isinstance(content, str):
            return [{"type": "text", "text": content}]
        return content
    
    def _merge_content(
        self, 
        existing_content: str | list[ContentPart], 
        new_content: str | list[ContentPart],
        before: bool = False
    ) -> str | list[ContentPart]:
        """
        Merges two content objects based on their types and the 'before' flag.
        
        Args:
            existing_content: The content of the message being merged into.
            new_content: The content from the insertion.
            before: If True, new_content is prepended; otherwise, it's appended.
        """
        # Case 1: Both are strings.
        if isinstance(existing_content, str) and isinstance(new_content, str):
            return new_content + existing_content if before else existing_content + new_content
        
        # Case 2: At least one is a list. Normalize both to lists and combine.
        existing_list = self._to_content_list(existing_content)
        new_list = self._to_content_list(new_content)
        
        return new_list + existing_list if before else existing_list + new_list

    def matchKeywords(self, keywords: list[str] | str, contents: str | list[str]) -> bool:
        """
        Checks if the content matches any of the keywords.
        
        Args:
            keywords: A list of keywords or a single keyword.
            content: The content to check.
        """
        if not keywords:
            return True
        
        if isinstance(contents, list):
            contents = "\n\n".join(contents)

        if isinstance(keywords, str):
            return keywords in contents
        else:
            return any(keyword in contents for keyword in keywords)
