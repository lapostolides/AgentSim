"""Shared test fixtures for AgentSim tests."""

import pytest

from agentsim.state.models import (
    AvailablePackage,
    EnvironmentInfo,
    ExperimentPlan,
    Hypothesis,
    LiteratureContext,
    LiteratureEntry,
    ParameterSpec,
)
from agentsim.state.transitions import (
    add_hypothesis,
    add_plan,
    set_environment,
    set_literature_context,
    start_experiment,
)


@pytest.fixture
def sample_environment():
    """A sample environment with simulation packages."""
    return EnvironmentInfo(
        packages=(
            AvailablePackage(name="numpy", version="1.26.0", import_name="numpy"),
            AvailablePackage(name="scipy", version="1.12.0", import_name="scipy"),
            AvailablePackage(name="matplotlib", version="3.8.0", import_name="matplotlib"),
        ),
        python_version="3.12.1",
    )


@pytest.fixture
def sample_hypothesis():
    """A sample structured hypothesis."""
    return Hypothesis(
        raw_text="Does increasing surface roughness reduce reconstruction accuracy?",
        formalized=(
            "Surface roughness is inversely correlated with "
            "NLOS reconstruction accuracy as measured by PSNR"
        ),
        variables=["roughness", "PSNR"],
        parameter_space=[
            ParameterSpec(name="roughness", values=[0.1, 0.3, 0.5, 0.7, 0.9]),
        ],
        predictions=["PSNR decreases as roughness increases"],
        assumptions=["Lambertian BRDF model", "Fixed camera geometry"],
    )


@pytest.fixture
def initial_state():
    """An initialized experiment state."""
    return start_experiment(
        "Does increasing surface roughness reduce reconstruction accuracy?",
        file_paths=[],
    )


@pytest.fixture
def sample_literature_context():
    """A sample literature context for grounding."""
    return LiteratureContext(
        entries=(
            LiteratureEntry(
                title="Surface Roughness Effects in Transient Imaging",
                authors=("Smith, J.", "Lee, K."),
                year=2021,
                key_findings=(
                    "Roughness above 0.5 significantly degrades reconstruction",
                    "Lambertian assumption breaks down for rough surfaces",
                ),
                relevance="Directly tests similar hypothesis with different method",
            ),
        ),
        summary="Prior work shows roughness degrades NLOS imaging quality.",
        open_questions=("How does roughness interact with material albedo?",),
        methodology_notes="Standard metrics: PSNR, SSIM. Typical sample sizes: 5-10 roughness levels.",
    )


@pytest.fixture
def state_with_hypothesis(initial_state, sample_hypothesis, sample_environment, sample_literature_context):
    """Experiment state with hypothesis, environment, and literature set."""
    state = set_environment(initial_state, sample_environment)
    state = set_literature_context(state, sample_literature_context)
    return add_hypothesis(state, sample_hypothesis)


@pytest.fixture
def state_with_plan(state_with_hypothesis, sample_hypothesis):
    """Experiment state with a plan ready."""
    plan = ExperimentPlan(
        hypothesis_id=sample_hypothesis.id,
        simulation_approach="Use numpy for synthetic data generation",
        scene_descriptions=[
            "Low roughness scene (0.1)",
            "Medium roughness scene (0.5)",
            "High roughness scene (0.9)",
        ],
        metrics=["PSNR", "SSIM"],
    )
    return add_plan(state_with_hypothesis, plan)
