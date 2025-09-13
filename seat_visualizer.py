import matplotlib.pyplot as plt
import streamlit as st

def visualize_seating(classroom_rows, classroom_cols, student_row, student_col):
    """
    Draw classroom seating layout with student's seat highlighted,
    using the same design (desks, board, door) as in the admin panel.
    """

    fig, ax = plt.subplots(figsize=(classroom_cols * 0.25, classroom_rows * 0.25), dpi=200)
    ax.set_facecolor("black")
    ax.set_aspect("equal")
    ax.axis("off")

    gap_x = 0.3
    desk_width = 1

    # --- Draw teacher's board (same as admin panel) ---
    desk_total_width = classroom_cols * (desk_width + gap_x)
    ax.add_patch(plt.Rectangle(
        (-0.5, classroom_rows + 0.3),
        desk_total_width + 0.5,
        1.2,
        facecolor="white",
        edgecolor="black",
        lw=1
    ))

    # --- Draw desks (semi-circle + rectangle) ---
    for r in range(classroom_rows):
        for c in range(classroom_cols):
            x = c * (desk_width + gap_x)
            y = classroom_rows - r - 1

            if r == student_row and c == student_col:
                seat_color = "limegreen"
                edge_width = 1
            else:
                seat_color = "#00CFFF"
                edge_width = 0.6

            # Desk rectangle (base)
            ax.add_patch(plt.Rectangle(
                (x + 0.1, y),
                0.8, 0.4,
                facecolor=seat_color,
                edgecolor="black",
                lw=edge_width
            ))

            # Desk semi-circle (top)
            ax.add_patch(plt.Circle(
                (x + 0.5, y + 0.5),
                0.4,
                facecolor=seat_color,
                edgecolor="black",
                lw=edge_width
            ))

    # --- Draw door ---
    ax.add_patch(plt.Rectangle(
        (-0.9, classroom_rows - 0.9),  
        0.6, 0.9,
        facecolor="brown",
        edgecolor="black",
        lw=0.8
    ))


    # --- Limits and layout ---
    ax.set_xlim(-1.2, classroom_cols + 2.7)
    ax.set_ylim(-0.8, classroom_rows + 1.6)
    plt.tight_layout(pad=0)

    st.pyplot(fig, clear_figure=True, use_container_width=True)
