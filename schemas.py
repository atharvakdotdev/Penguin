JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string"
        },
        "status": {
            "type": "string",
            "enum": [
                "in_progress",
                "finished"
            ]
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "info",
                            "analysis",
                            "command",
                            "verification"
                        ]
                    },
                    "title": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "command": {
                        "type": "string"
                    },
                    "run": {
                        "type": "boolean"
                    },
                    "requires_sudo": {
                        "type": "boolean"
                    }
                },
                "required": [
                    "type",
                    "title"
                ]
            }
        }
    },
    "required": [
        "reply",
        "status",
        "steps"
    ]
}