JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reply",
        "decision",
        "steps",
        "investigation_update"
    ],
    "properties": {

        "reply": {
            "type": "string",
            "description": "Natural language shown to the user. Never include shell commands."
        },

        "decision": {
            "type": "string",
            "enum": [
                "understand",
                "hypothesis",
                "diagnose",
                "solve",
                "verify",
                "finished"
            ]
        },

        "steps": {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,

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
            "title",
            "description"
        ],

        "allOf": [
            {
                "if": {
                    "properties": {
                        "type": {
                            "const": "command"
                        }
                    }
                },
                "then": {
                    "required": [
                        "command",
                        "run",
                        "requires_sudo"
                    ]
                }
            },
            {
                "if": {
                    "properties": {
                        "type": {
                            "const": "verification"
                        }
                    }
                },
                "then": {
                    "required": [
                        "command",
                        "run"
                    ]
                }
            }
        ]
    }
},

        "investigation_update": {
            "type": "object",
            "additionalProperties": True,
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
                        "additionalProperties": False,
                        "required": [
                            "key",
                            "value"
                        ],
                        "properties": {

                            "key": {
                                "type": "string"
                            },

                            "value": {},

                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
                            }
                        }
                    }
                },

                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": [
                            "name",
                            "confidence",
                            "status"
                        ],
                        "properties": {

                            "name": {
                                "type": "string"
                            },

                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1
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
                        }
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
        }
    }
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