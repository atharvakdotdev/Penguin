JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string"
        },

        "thinking": {
            "type": "string",
            "description": "Short internal reasoning summary. Never reveal chain-of-thought. Explain conclusions only."
        },

        "decision": {
            "type": "string"
        },

        "investigation_update": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string"
                },

                "next_goal": {
                    "type": "string"
                },

                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },

                "root_cause": {
                    "type": ["string", "null"]
                },

                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string"
                            },
                            "value": {},
                            "confidence": {
                                "type": "number"
                            }
                        },
                        "required": [
                            "key",
                            "value"
                        ]
                    }
                },

                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string"
                            },
                            "confidence": {
                                "type": "number"
                            },
                            "status": {
                                "type": "string",
                                "enum": [
                                    "possible",
                                    "likely",
                                    "confirmed",
                                    "rejected"
                                ]
                            },
                            "reason": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "name",
                            "confidence",
                            "status"
                        ]
                    }
                },

                "questions": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },

                "solution": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                }
            }
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
        "decision",
        "steps"
    ]
}

history = {
    "system_prompt": "",

    "issue": {
        "description": "",
        "goal": "",
        "severity": None,
        "status": "investigating"
    },

    "system": {
        "os": None,
        "distribution": None,
        "kernel": None,
        "shell": None,
        "package_manager": None,
        "hostname": None
    },

    "facts": {
        # Proven facts only
        "nvim_installed": None,
        "path_contains_nvim": None,
        "internet_available": None
    },

    "hypotheses": [
        {
            "name": "",
            "confidence": 0.0,
            "status": "possible"   # possible / confirmed / rejected
        }
    ],

    "commands": [
        {
            "command": "",
            "success": True,
            "output": "",
            "timestamp": "",
            "reason": ""
        }
    ],

    "pending_action": None,

    "pending_confirmation": False,

    "solution": [
        "sudo apt update",
        "sudo apt install neovim"
    ],

    "last_user_message": "",

    "summary": ""
}