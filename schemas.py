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

        "is_continue": {
            "type": "boolean"
        },

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
            "additionalProperties": False,
            "required": [
                "next_goal"
            ],
            "properties": {

                "issue": {
                    "type": "string"
                },

                "summary": {
                    "type": "string"
                },

                "status": {
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
                        "additionalProperties": False,
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

                "pending_questions": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },

                "questions_asked": {
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
                },

                "executed_commands": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "command",
                            "success",
                            "output",
                            "timestamp"
                        ],
                        "properties": {
                            "command": {
                                "type": "string"
                            },
                            "success": {
                                "type": "boolean"
                            },
                            "output": {
                                "type": "string"
                            },
                            "timestamp": {
                                "type": "string"
                            }
                        }
                    }
                }
            }
        }
    },

    "allOf": [
        {
            "if": {
                "properties": {
                    "decision": {"const": "hypothesis"}
                }
            },
            "then": {
                "properties": {
                    "investigation_update": {
                        "required": ["facts", "hypotheses"],
                        "properties": {
                            "facts": {"minItems": 1},
                            "hypotheses": {"minItems": 1}
                        }
                    }
                }
            }
        },
        {
            "if": {
                "properties": {
                    "decision": {"const": "diagnose"}
                }
            },
            "then": {
                "properties": {
                    "investigation_update": {
                        "required": ["facts", "hypotheses"],
                        "properties": {
                            "facts": {"minItems": 1},
                            "hypotheses": {"minItems": 1}
                        }
                    }
                }
            }
        }
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

understand_schema = {
  "type": "object",
  "properties": {
    "problem_statement": {
      "type": "string",
      "description": "A clear, concise, technically precise description of the user's problem, based only on the user query and provided logs."
    }
  },
  "required": [
    "problem_statement"
  ],
  "additionalProperties": False
}
hypothesis_schema={
  "type": "object",
  "properties": {
    "hypotheses": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "hypothesis": {
            "type": "string"
          },
          "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
          }
        },
        "required": [
          "id",
          "hypothesis",
          "confidence"
        ],
        "additionalProperties": False
      }
    }
  },
  "required": [
    "hypotheses"
  ],
  "additionalProperties": False
}
command_test_schema = {
  "type": "object",
  "properties": {
    "tests": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "command": {
            "type": "string"
          },
          "purpose": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "command",
          "purpose"
        ],
        "additionalProperties": False
      }
    }
  },
  "required": [
    "tests"
  ],
  "additionalProperties": False
}

facts_schema = {
  "type": "object",
  "properties": {
    "facts": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "fact": {
            "type": "string"
          },
          "source": {
            "type": "string",
            "description": "The command or input that directly supports this fact."
          }
        },
        "required": [
          "id",
          "fact",
          "source"
        ],
        "additionalProperties": False
      }
    }
  },
  "required": [
    "facts"
  ],
  "additionalProperties": False
}

solver_scheme = {
    "type": "object",
    "additionalProperties": False,
    "required": ["step"],
    "properties": {
        "step": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "type",
                "title",
                "purpose",
                "command",
                "run",
                "requires_sudo"
            ],
            "properties": {
                "type": {
                    "type": "string",
                    "const": "command"
                },

                "title": {
                    "type": "string"
                },

                "purpose": {
                    "type": "string"
                },

                "command": {
                    "type": "string"
                },

                "run": {
                    "type": "boolean",
                    "const": True
                },

                "requires_sudo": {
                    "type": "boolean"
                }
            }
        }
    }
}
verification_scheme = {
    "type": "object",
    "additionalProperties": False,
    "required": ["step"],
    "properties": {
        "step": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "type",
                "title",
                "purpose",
                "command",
                "run"
            ],
            "properties": {
                "type": {
                    "type": "string",
                    "const": "verification"
                },
                "title": {
                    "type": "string"
                },
                "purpose": {
                    "type": "string"
                },
                "command": {
                    "type": "string",
                    "minLength": 1
                },
                "run": {
                    "type": "boolean",
                    "const": True
                }
            }
        }
    }
}
verification2_scheme = {
    "type": "object",
    "additionalProperties": False,
    "required": ["solved"],
    "properties": {
        "solved": {
            "type": "boolean"
        }
    }
}
check_diagnosis_scheme = {
    "type": "object",
    "additionalProperties": False,
    "required": ["contradicts"],
    "properties": {
        "contradicts": {
            "type": "boolean"
        }
    }
}