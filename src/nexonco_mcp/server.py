import os
from collections import Counter
from typing import Optional

import pandas as pd
import uvicorn
from smithery.decorators import smithery
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

from .api import CivicAPIClient

API_VERSION = "0.1.19"
BUILD_TIMESTAMP = "2025-12-31"


@smithery.server()
def create_server() -> FastMCP:
    """Create and configure the Nexonco MCP server for Smithery deployment.

    This function is decorated with @smithery.server() to enable automatic
    discovery and deployment by the Smithery platform.

    Returns:
        FastMCP: Configured MCP server instance with clinical evidence tools.
    """
    # Create FastMCP instance for Smithery
    mcp = FastMCP(
        name="nexonco",
        instructions="An advanced MCP Server for accessing and analyzing clinical evidence data, with flexible search options to support precision medicine and oncology research.",
    )

    @mcp.tool(
        name="search_clinical_evidence",
        description=(
            "Perform a flexible search for clinical evidence using combinations of filters such as disease, therapy, "
            "molecular profile, phenotype, evidence type, and direction. This flexible search system allows you to tailor "
            "your query based on the data needed for research or clinical decision-making. It returns a detailed report that "
            "includes summary statistics, a top 10 evidence listing, citation sources, and a disclaimer."
        ),
    )
    def search_clinical_evidence(
        disease_name: Optional[str] = Field(
            default="",
            description="Name of the disease to filter evidence by (e.g., 'Von Hippel-Lindau Disease', 'Lung Non-small Cell Carcinoma', 'Colorectal Cancer', 'Chronic Myeloid Leukemia', 'Glioblastoma'..). Case-insensitive and optional.",
        ),
        therapy_name: Optional[str] = Field(
            default="",
            description="Therapy or drug name involved in the evidence (e.g., 'Cetuximab', 'Imatinib', 'trastuzumab', 'Lapatinib'..). Optional.",
        ),
        molecular_profile_name: Optional[str] = Field(
            default="",
            description="Molecular profile or gene name or variant name (e.g., 'EGFR L858R', 'BRAF V600E', 'KRAS', 'PIK3CA'..). Optional.",
        ),
        phenotype_name: Optional[str] = Field(
            default="",
            description="Name of the phenotype or histological subtype (e.g., 'Hemangioblastoma', 'Renal cell carcinoma', 'Retinal capillary hemangioma', 'Pancreatic cysts', 'Childhood onset'..). Optional.",
        ),
        evidence_type: Optional[str] = Field(
            default="",
            description="Evidence classification: 'PREDICTIVE', 'DIAGNOSTIC', 'PROGNOSTIC', 'PREDISPOSING', or 'FUNCTIONAL'. Optional.",
        ),
        evidence_direction: Optional[str] = Field(
            default="",
            description="Direction of the evidence: 'SUPPORTS' or 'DOES_NOT_SUPPORT'. Indicates if the evidence favors the association.",
        ),
        filter_strong_evidence: bool = Field(
            default=False,
            description="If set to True, only evidence with a rating above 3 will be included, indicating high-confidence evidence. However, the number of returned evidence items may be quite low.",
        ),
    ) -> str:
        """
        Query clinical evidence records using flexible combinations of disease, therapy, molecular profile,
        phenotype, and other evidence characteristics. Returns a formatted report containing a summary of findings,
        most common genes and therapies, and highlights of top-ranked evidence entries including source URLs and citations.

        This tool is designed to streamline evidence exploration in precision oncology by adapting to various research
        or clinical inquiry contexts.

        Returns:
            str: A human-readable report summarizing relevant evidence, key statistics, and literature references.
        """

        client = CivicAPIClient()

        disease_name = None if disease_name == "" else disease_name
        therapy_name = None if therapy_name == "" else therapy_name
        molecular_profile_name = (
            None if molecular_profile_name == "" else molecular_profile_name
        )
        phenotype_name = None if phenotype_name == "" else phenotype_name
        evidence_type = None if evidence_type == "" else evidence_type
        evidence_direction = None if evidence_direction == "" else evidence_direction

        df: pd.DataFrame = client.search_evidence(
            disease_name=disease_name,
            therapy_name=therapy_name,
            molecular_profile_name=molecular_profile_name,
            phenotype_name=phenotype_name,
            evidence_type=evidence_type,
            evidence_direction=evidence_direction,
            filter_strong_evidence=filter_strong_evidence,
        )

        if df.empty:
            return "No evidence found for the specified filters."

        # ---------------------------------
        # 1. Summary Statistics Section
        # ---------------------------------
        total_items = len(df)
        avg_rating = df["evidence_rating"].mean()

        # Frequency counters for each key attribute
        disease_counter = Counter(df["disease_name"].dropna())
        gene_counter = Counter(df["gene_name"].dropna())
        variant_counter = Counter(df["variant_name"].dropna())
        therapy_counter = Counter(df["therapy_names"].dropna())
        phenotype_counter = Counter(df["phenotype_name"].dropna())

        # Prepare top-3 summary for each attribute
        def format_top(counter: Counter) -> str:
            return (
                ", ".join(f"{item} ({count})" for item, count in counter.most_common(3))
                if counter
                else "N/A"
            )

        top_diseases = format_top(disease_counter)
        top_genes = format_top(gene_counter)
        top_variants = format_top(variant_counter)
        top_therapies = format_top(therapy_counter)
        top_phenotypes = format_top(phenotype_counter)

        stats_section = (
            f"**Summary Statistics**\n"
            f"- Total Evidence Items: {total_items}\n"
            f"- Average Evidence Rating: {avg_rating:.2f}\n"
            f"- Top Diseases: {top_diseases}\n"
            f"- Top Genes: {top_genes}\n"
            f"- Top Variants: {top_variants}\n"
            f"- Top Therapies: {top_therapies}\n"
            f"- Top Phenotypes: {top_phenotypes}\n"
        )

        # ---------------------------------
        # 2. Top 10 Evidence Listing Section
        # ---------------------------------
        top_evidences = df.sort_values(by="evidence_rating", ascending=False).head(10)
        evidence_section = "**Top 10 Evidence Entries**\n"
        for _, row in top_evidences.iterrows():
            evidence_section += (
                f"\n**{row.get('evidence_type', 'N/A')} ({row.get('evidence_direction', 'N/A')})** | Rating: {row.get('evidence_rating', 'N/A')}\n"
                f"- Disease: {row.get('disease_name', 'N/A')}\n"
                f"- Phenotype: {row.get('phenotype_name', 'N/A')}\n"
                f"- Gene/Variant: {row.get('gene_name', 'N/A')} / {row.get('variant_name', 'N/A')}\n"
                f"- Therapy: {row.get('therapy_names', 'N/A')}\n"
                f"- Description: {row.get('description', 'N/A')}\n"
            )

        # ---------------------------------
        # 3. Sources & Citations Section
        # ---------------------------------
        citation_section = "**Sources & Citations**\n"
        sources = client.get_sources(top_evidences["id"].tolist())
        for _, row in pd.DataFrame(sources).iterrows():
            citation_section += (
                f"- {row.get('citation', 'N/A')} - {row.get('sourceUrl', 'N/A')}\n"
            )

        # ---------------------------------
        # 4. Disclaimer Section
        # ---------------------------------
        disclaimer = "\n**Disclaimer:** This tool is intended exclusively for research purposes. It is not a substitute for professional medical advice, diagnosis, or treatment."

        # ---------------------------------
        # Combine All Sections into Final Report
        # ---------------------------------
        final_report = (
            f"{stats_section}\n"
            f"{evidence_section}\n"
            f"{citation_section}\n"
            f"{disclaimer}"
        )

        return final_report

    return mcp


def main():
    """Run the MCP server with HTTP transport for Smithery deployment.

    The server listens on the PORT environment variable (default 8080).
    Smithery sets PORT to 8081 when deployed.
    """
    mcp = create_server()

    # Get port from environment (Smithery sets this to 8081)
    port = int(os.environ.get("PORT", 8080))

    # Create Starlette app with CORS middleware for cross-origin requests
    app = Starlette(
        routes=[
            Mount("/", app=mcp.sse_app()),
        ],
    )

    # Add CORS middleware to allow requests from any origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Run the HTTP server
    uvicorn.run(app, host="0.0.0.0", port=port)


def main_stdio():
    """Run the MCP server with stdio transport for local development."""
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
