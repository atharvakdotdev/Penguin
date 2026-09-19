
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
hypothesis_schema = {
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
                    },
                    "result": {
                        "type": "string",
                        "enum": [
                            "confirmed",
                            "contradicted",
                            "already_resolved",
                        ]
                    }
                },
                "required": [
                    "id",
                    "hypothesis",
                    "confidence",
                    "result"
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
    "required": ["reason", "solved"],
    "properties": {
        "reason": {
            "type": "string",
            "description": (
                "1-2 lines max: what the command output shows and whether it "
                "confirms or contradicts the original problem being solved. "
                "Base this only on the actual output/error content, not on "
                "return_code or success alone."
            )
        },
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
decideOnuserMsg={
  "type": "object",
  "additionalProperties": False,
  "required": [
    "impact",
    "affected",
    "action"
  ],
  "properties": {
    "impact": {
      "type": "string",
      "enum": [
        "none",
        "new_fact",
        "clarification",
        "contradiction",
        "test_result",
        "constraint",
        "problem_change",
        "solved"
      ]
    },
    "affected": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": True,
      "items": {
        "type": "string",
        "enum": [
          "none",
          "problem",
          "facts",
          "hypothesis",
          "diagnosis",
          "solution",
          "verification",
          "execution"
        ]
      }
    },
    "action": {
      "type": "string",
      "enum": [
        "continue",
        "reassess",
        "stop"
      ]
    }
  }
}