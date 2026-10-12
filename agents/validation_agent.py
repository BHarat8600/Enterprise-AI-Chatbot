from models.schemas import ToolResult


class ValidationAgent:
    name = "validation"

    def validate_tool_results(self, results: list[ToolResult]) -> list[str]:
        issues: list[str] = []
        for result in results:
            if not result.success:
                issues.append(f"{result.tool.value} failed: {result.error}")
            if result.success and result.output in (None, "", []):
                issues.append(f"{result.tool.value} returned no usable data")
        return issues

